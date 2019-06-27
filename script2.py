# https://nbviewer.jupyter.org/github/craffel/midi-dataset/blob/master/Tutorial.ipynb

import tables
import lmd
import json
import numpy as np
import pandas as pd
import re
import pdb, traceback, sys
import time
from script import notes, maj_scale


keys = notes
# en la tonalidad de do algunos sostenidos es mejor escribirlos como bemoles
notes_C = {note: note for note in notes}
notes_C['D#'] = 'Eb'
notes_C['G#'] = 'Ab'
notes_C['A#'] = 'Bb'

min_scale = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0]
rel_minors = {}
for i, key in enumerate(keys):
    # the minor key starts three semitones below its relative major
    rel_minors[key] = keys[i - 3]
modes = ['minor', 'major']

# intervals = ['P1', 'm2', 'M2', 'm3', 'M3', 'P4', 'TT', 'P5', 'm6', 'M6', 'm7', 'M7']
# nodes = []
# numerals = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii']
# maj_triad = [0, 4, 7]
# min_triad = [0, 3, 7]
# c_maj_scale = [note for i, note in enumerate(notes) if maj_scale[i]]
# c_min_scale = [note for i, note in enumerate(notes) if min_scale[i]]
# for i, numeral in enumerate(numerals):
#     nodes.append(
#         ''.join(
#             sorted(
#                 np.roll(c_maj_scale, -i)[[0, 2, 4]]
#             )
#         )
#     )
#     nodes.append(
#         ''.join(
#             sorted(
#                 np.roll(c_min_scale, -i)[[0, 2, 4]]
#             )
#         )
#     )
# nodes.append('*')  # otros acordes no especificados
# nodes.append('n')  # silencio

family_ignore = ['Sound Effects']
monophony_threshold = .8
# mínima proporción de beats sonoros para usar track como bajo
length_threshold = .25


class Song():
    def __init__(self, msd_id, midis):
        self.msd_id = msd_id
        self.midis = midis
        self.h5 = lmd.msd_id_to_h5(msd_id)
        with tables.open_file(self.h5) as h5:
            self.title = h5.root.metadata.songs.cols.title[0].decode()
            self.artist = h5.root.metadata.songs.cols.artist_name[0].decode()
            self.artist_terms = h5.root.metadata.artist_terms[:].astype(str).tolist()
            self.year = h5.root.musicbrainz.songs.cols.year[0]  # ?
            self.hotness = h5.root.metadata.songs.cols.song_hotttnesss[0]
            self.key_echonest = {
                'key': (keys+[None])[h5.root.analysis.songs.cols.key[0]],
                'confidence': h5.root.analysis.songs.cols.key_confidence[0]
            }
            self.mode = {
                'mode': (modes+[None])[h5.root.analysis.songs.cols.mode[0]],
                'confidence': h5.root.analysis.songs.cols.mode_confidence[0]
            }
        self.best_bnc = self.get_best_bnc()  # se puede indicar umbral de score
        # alternativamente, podemos usar lista de bnc's (todos o subconjunto)
        self.key = self.get_key()
        # self.adj_matrix = self.get_adj_matrix()

    def get_best_bnc(self, score_threshold=0):
        # bnc del archivo midi con mejor score
        bncs = [
            (
                lmd.get_midi_path(self.msd_id, midi_md5, 'matched') + '.bnc',
                score
            )
            for midi_md5, score
            in sorted(self.midis.items(), key=lambda midi: midi[1])
            if score > score_threshold
        ]
        best_bnc, best_score = bncs[0]
        return BNCFile(best_bnc, best_score)

    def get_key(self):
        # to-do: sin terminar
        # from collections import Counter
        # midi_key_signatures = Counter(self.best_bnc.key_signatures)
        # if len(midi_key_signatures) > 0:
        #     if (
        #         # si Cmaj es la única armadura es probable que sea default
        #         ('C' not in midi_key_signatures) or \
        #         (len(midi_key_signatures) > 1)
        #     ):
        #         # si hay más de una, devuelve la más frecuente
        #         # si hay empate, devuelve una arbitrariamente
        #         midi_key = midi_key_signatures.most_common()[0][0]
        # if self.best_bnc.bass_track:
        #     pass
        # echonest, según confianza
        # best_key + max_chord (para definir modo)
        # best_key major
        return self.key_echonest['key']

    def _get_adj_matrix(self):
        polyphonic_tracks = self.best_bnc.polyphonic
        if len(polyphonic_tracks) > 0:
            adj_matrix = pd.DataFrame(
                np.full([len(nodes), len(nodes)], 0),
                index=nodes,
                columns=nodes
            )
            weight = 1 / len(polyphonic_tracks)
            for track in polyphonic_tracks:
                adj_matrix = track.update_adj_matrix(
                    adj_matrix, self.key, weight
                )
        else:
            adj_matrix = None
        return adj_matrix

    def get_adj_matrix(self, grand_matrix=None):
        adj_matrices = {}
        if grand_matrix is not None:
            adj_matrices['grand_matrix'] = grand_matrix
        polyphonic_tracks = self.best_bnc.polyphonic
        if len(polyphonic_tracks) > 0:
            adj_matrices['adj_matrix'] = {}
            for track in polyphonic_tracks:
                beats = track.beats['pitch_class']
                weight = 1 / len(polyphonic_tracks) / len(beats)
                for i, beat in enumerate(beats):
                    if len(beats) > i + 1:
                        from_beat = normalize_beat(beats[i], key)
                        to_beat = normalize_beat(beats[i + 1], key)
                        for adj_matrix in adj_matrices:
                            if from_beat not in adj_matrices[adj_matrix]:
                                adj_matrices[adj_matrix][from_beat] = {}
                            if to_beat not in adj_matrices[adj_matrix][from_beat]:
                                adj_matrices[adj_matrix][from_beat][to_beat] = 0
                            adj_matrices[adj_matrix][from_beat][to_beat] += weight
        else:
            adj_matrices['adj_matrix'] = None
        self.adj_matrix = adj_matrices['adj_matrix']
        if grand_matrix is not None:
            return adj_matrices['grand_matrix']

    def write_adj_matrix(self):
        fileout = self.best_bnc.midi_file + '.mat'
        with open(fileout, 'w') as csvfile:
            csvfile.write('Título: ' + self.title + '\n')
            csvfile.write('Artista: ' + self.artist + '\n')
            csvfile.write('Año: ' + str(self.year) + '\n')
            csvfile.write('Tonalidad (Echo Nest): ' + self.key + '\n')
            # csvfile.write('Tempo: ' + self.best_bnc.)
            df = pd.DataFrame(self.adj_matrix).fillna(0)
            df = df.reindex(index=sorted(df.index), columns=sorted(df.columns))
            df.to_csv(csvfile)
        # permite jugar con un tercer script que combina matrices
        # según género, año, etc
        # incluir cómo se obtuvo key
        # incluir ruta midi y score


class BNCFile():
    def __init__(self, bnc, match_score):
        import csv
        import codecs
        self.midi_file = bnc.replace('.bnc', '')
        self.match_score = match_score
        self.key_signatures = []
        self.monophonic = []
        self.polyphonic = []
        with codecs.open(bnc, 'rb', 'utf-8') as csvfile:
            # https://stackoverflow.com/questions/4166070/python-csv-error-line-contains-null-byte
            reader = csv.DictReader(csvfile)
            for track in reader:
                if re.match(r'^Meta Track ', track['track_name']):
                    meta_type = track['track_name'].split(' ')[-1]
                    if meta_type == 'key_signature':
                        self.key_signatures = track['beats'].split('|')
                else:
                    note_track = NoteTrack(track)
                    if (
                        note_track.instrument_families not in family_ignore and
                        not note_track.is_empty
                    ):
                        if note_track.monophony > monophony_threshold:
                            self.monophonic.append(note_track)
                        else:
                            self.polyphonic.append(note_track)
        self.bass_track = self.get_bass_track()

    def get_bass_track(self):
        long_monophonic = [
            track for track in self.monophonic
            if track.sound_ratio > length_threshold
        ]
        bass_track = None
        if len(long_monophonic) > 0:
            min_pitch_mean = 127
            for track in long_monophonic:
                if track.pitch_mean < min_pitch_mean:
                    min_pitch_mean = track.pitch_mean
                    bass_track = track
        return bass_track


class NoteTrack():
    def __init__(self, track):
        self.instrument_families = track['families'].split('&')
        self.monophony = float(track['monophony'])
        key_pattern = re.compile(r'[ABCDEFG]#?')
        self.key = {
            'max_note_on': key_pattern.findall(track['max_note_on']),
            'max_note_chord': key_pattern.findall(track['max_note_chord']),
            'best_key_signature': key_pattern.findall(
                track['best_key_signature']
            )
        }
        self.beats = {
            'pitch_mean': [],
            'pitch_class': []
        }
        self.pitch_mean = None
        self.sound_ratio = None
        beat_pattern = re.compile(
            r'(?P<class>[ABCDEFG]#?)(?P<octave>-?\d?)'
        )
        beats = track['beats'].split('|')
        if len(beats) > 0:
            self.is_empty = False
            for beat in beats:
                beat_pitch = set()
                pitch_class = set()
                sound_beat_count = 0
                for pitch in beat_pattern.finditer(beat):
                    pitch_class.add(pitch['class'])
                    beat_pitch.add(
                        note2int(pitch['class'], int(pitch['octave']))
                    )
                pitch_mean = np.mean(list(beat_pitch))
                self.beats['pitch_mean'].append(pitch_mean)
                self.beats['pitch_class'].append(pitch_class)
                if len(pitch_class) > 0:
                    sound_beat_count += 1
            self.pitch_mean = np.nanmean(self.beats['pitch_mean'])
            self.sound_ratio = sound_beat_count / len(beats)
        else:
            self.is_empty = True

    def _update_adj_matrix(self, adj_matrix, key, weight=1):
        beats = self.beats['pitch_class']
        weight = weight / len(beats)  # tracks con len(beats) = 0 no llegan
        for i, beat in enumerate(beats):
            if len(beats) > i + 1:
                edge = ['*', '*']
                from_beat = normalize_beat(beats[i], key)
                to_beat = normalize_beat(beats[i + 1], key)
                for i, node in enumerate([from_beat, to_beat]):
                    if node in nodes:
                        edge[i] = node
                    elif not node:
                        edge[i] = 'n'
                adj_matrix.loc[edge[0], edge[1]] += weight
        return adj_matrix


def note2int(pitch_class, octave):
    note_int = (octave+1)*12 + notes.index(pitch_class)
    return note_int


def _normalize_beat(beat, key):
    offset = keys.index(key)
    norm_beat = set()
    for pitch_class in beat:
        norm_beat.add(np.roll(notes, offset)[notes.index(pitch_class)])
    # norm_beat = ''.join([note for note in notes if note in norm_beat])
    norm_beat = ''.join(sorted(norm_beat))
    return norm_beat


def normalize_beat(beat, key):
    # lleva todo a tonalidad C
    offset = keys.index(key)
    norm_beat = set()
    for pitch_class in beat:
        norm_pitch_class = np.roll(notes, offset)[notes.index(pitch_class)]
        norm_pitch_class = notes_C[norm_pitch_class]
        norm_beat.add(norm_pitch_class)
    if len(norm_beat) == 0:
        # beat silencioso
        norm_beat.add('n')
    # norm_beat = ''.join([note for note in notes if note in norm_beat])
    norm_beat = ''.join(sorted(norm_beat))
    return norm_beat


def save(file_count, adj_matrix):
    df = pd.DataFrame(adj_matrix).fillna(0)
    df = df.reindex(index=sorted(df.index), columns=sorted(df.columns))
    with open('grand_matrix.mat', 'w') as fileout:
        fileout.write('File count: ' + str(file_count) + '\n')
        df.to_csv(fileout)
    return len(df)


grand_matrix = {}
# to-do: la matriz para cada archivo no es tan grande
# pero a medida que se van sumando sí (aunque debería aplanarse)
# lo ideal sería trabajar con una matriz rala
step = 50
file_count = 0
with open(lmd.SCORE_FILE) as f:
    scores = json.load(f)
    t = time.time()
    for msd_id, midis in scores.items():
        try:
            song = Song(msd_id, midis)
            grand_matrix = song.get_adj_matrix(grand_matrix)
            if song.adj_matrix is not None:
                song.write_adj_matrix()
                file_count += 1
            else:
                print(
                    'Matriz de adyacencia vacía, ' +
                    song.best_bnc.midi_file +
                    '.mat',
                    file=sys.stderr
                )
        except KeyboardInterrupt:
            break
        except:
            print(msd_id, file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
        if file_count % step == 0:
            node_count = save(file_count, grand_matrix)
            print(
                'Se procesaron {} archivos en {:.2f} segundos. '
                'Van {} archivos, y la matriz de adyacencia '
                'tiene {} nodos!'.format(
                    step,
                    time.time() - t,
                    file_count,
                    node_count
                )
            )
            t = time.time()
            sys.stderr.flush()
            # pdb.set_trace()
_ = save(file_count, grand_matrix)

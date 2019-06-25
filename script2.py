# https://nbviewer.jupyter.org/github/craffel/midi-dataset/blob/master/Tutorial.ipynb

import tables
import lmd
import json
import numpy as np
import pdb


keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B', None]
modes = ['minor', 'major', None]
nodes = []  # nodos del grafo a los que vamos a ajustar cada binned n-chord


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
                'key': keys[h5.root.analysis.songs.cols.key[0]],
                'confidence': h5.root.analysis.songs.cols.key_confidence[0]
            }
            self.mode = {
                'mode': modes[h5.root.analysis.songs.cols.mode[0]],
                'confidence': h5.root.analysis.songs.cols.mode_confidence[0]
            }
        self.adj_matrix = np.full([len(nodes), len(nodes)], 0)
        self.best_bnc = self.get_best_bnc()  # se puede indicar umbral de score
        # alternativamente, podemos usar lista de bnc's (todos o subconjunto)

    def get_best_bnc(self, score_threshold=0):
        # bnc del archivo midi con mejor score
        best_bnc = [
            lmd.get_midi_path(self.msd_id, midi_md5, 'matched')
            for midi_md5, score
            in sorted(self.midis.items(), key=lambda midi: midi[1])
            if score > score_threshold
        ][0]
        return BNCFile(best_bnc)

    def write_adj_matrix(self):
        # escribe matriz de adyacencia al disco;
        # incluye título, artista, año y otra metadata;
        # permite jugar con un tercer script que combina matrices
        # según género, año, etc
        pass


class BNCFile():
  def __init__(self, bnc):
    self.tracks = []


class NoteTrack():
  def __init__(self, track):
    import re
    self.instrument_family = track.family
    self.mean_octave = None
    self.beats = []
    self.tonality = {
        # 'max_note_on': track.max_note_on,
        # ...
    }
    # se podría pedir un índce de confianza para tonalidades de script1
    # ojo con key_signatures script1: si Cmaj es probable que sea por default

    for beat in track.beats.split('|'):
      for note in re.match(r'([])(#?)(/d)', beat):
        note
        # conviene promediar octava por beat o promediar todo al final?


with open(lmd.SCORE_FILE) as f:
    scores = json.load(f)
    for msd_id, midis in scores.items():
        song = Song(msd_id, midis)
        pdb.set_trace()

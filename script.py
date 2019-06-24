import mido
import numpy as np
from collections import Counter
import pdb
# first check file type
# if mid.file == 1, one track per instrument

notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
maj_scale = [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1]
meta_ignore = ['time_signature', 'midi_port', 'end_of_track', 'track_name']


class Track:
  def __init__(self, track, tpb, length):
    # to-do: algunos tracks podrían tener más de un channel (hasta 16)
    # habría que tratar cada channel como un track separado;
    # esto es especialmente relevante en archivos tipo 0, con un solo track
    self.name = track.name.strip()
    self.channels = set()
    self.ch10 = False
    self.programs = set()
    self.monophony = None
    self._chords = {}
    # cuenta cuántas veces se toca (note_on) cada nota:
    self._note_on_count = np.zeros(len(notes), dtype=int)
    self.max_note_on = None
    self.max_note_chord = None
    self.best_key_signatue = None
    self.beats = None
    self.bpms = []
    self.parse(track, tpb, length)
    if len(self.channels) > 1:
      print('Advertencia: Más de un canal por pista.')
    self.ch10 = 10 in self.channels  # channel 10 is reserved for percussion
    if len(self.programs) > 1:
      print('Advertencia: Más de un programa por pista.')
    if self._note_on_count.sum() > 0:
      self.monophony = self.get_monophony()
      self.max_note_on = self.get_max_note_on()
      self.max_note_chord = self.get_max_note_chord()
      self.best_key_signature = self.get_best_key_signature()

  def parse(self, track, tpb, length):
    beats = []
    notes_on = set()
    beat_idx = 0
    for msg in track:
      if not msg.is_meta:
        self.channels.add(msg.channel)
        beat_idx += msg.time / tpb
        while beat_idx >= len(beats):
          beats.append(notes_on.copy())
        if msg.type == 'note_on':
          notes_on.add(msg.note)
          self._note_on_count[msg.note%12] += 1
        elif msg.type == 'note_off':
          notes_on.remove(msg.note)
        elif msg.type == 'program_change':
          self.programs.add(msg.program)
        else:
          # unexpected midi msg
          print(msg)
        self._chords[beat_idx] = notes_on.copy()
        beats[-1] |= notes_on
      else:
        # msg is meta
        if msg.type == 'set_tempo':
          self.bpms.append(1/msg.tempo*1e6*60)
        elif msg.type in meta_ignore:
          pass
        else:
          print(msg)
    # llevar todos los tracks a la longitud del TempoTrack
    while length > len(beats):
      beats.append(notes_on.copy())
    if len(notes_on):
      print('Advertencia: Algunas notas siguen sonando al final de la pista.')
    self.beats = [
        ''.join([int2note(note) for note in sorted(beat)])
        for beat in beats
    ]

  def get_monophony(self):
    # esto debería ser sobre total de no silencios
    # porque un track puede permanecer en silencio gran parte del tema
    chords = self._chords
    monophonic = [chord for chord in chords.values() if len(chord) == 1]
    phonic = [chord for chord in chords.values() if len(chord) > 0]
    monophony = len(monophonic) / len(phonic)
    return monophony

  def get_max_note_on(self):
    # nota tocada más veces (note_on)
    note_on_count = self._note_on_count
    max_note_on = ''.join([
        notes[i] for i, count in enumerate(note_on_count)
        if count == max(note_on_count)
    ])
    return max_note_on

  def get_max_note_chord(self):
    # nota presente en la mayor cantidad de "acordes" (chords)
    chords = self._chords
    chord_note_count = Counter([
        notes[note % 12] for chord in chords.values() for note in chord
    ])
    max_note_chord = ''.join(sorted([
        note for note, count in chord_note_count.items()
        if count == max(chord_note_count.values())
    ]))
    return max_note_chord

  def get_best_key_signature(self):
    # Minimización de alteraciones
    # proporción de notas fuera de la escala para cada armadura
    note_on_count = self._note_on_count
    offscale_ratios = np.full(len(notes), None)
    for i, note in enumerate(notes):
      scale_notes = np.roll(maj_scale, -i)  # traslada el patrón de la escala
      offscale_ratios[i] = 1 - (note_on_count * scale_notes).sum() / note_on_count.sum()
    best_key_signature = ''.join([
        notes[i] for i, ratio in enumerate(offscale_ratios)
        if ratio == min(offscale_ratios)
    ])
    return best_key_signature


class TempoTrack:
  def __init__(self, track, tpb):
    beats = []
    bpm = 120
    beat_idx = 0
    for msg in track:
      if not msg.is_meta:
        raise Exception('Error: Sólo se admiten eventos Meta en el TempoTrack')
      else:
        beat_idx += msg.time / tpb
        while beat_idx >= len(beats):
          beats.append(bpm)
        if msg.type == 'set_tempo':
          bpm = 1/msg.tempo*1e6*60
        elif msg.type in meta_ignore:
          pass
        else:
          # unexpected meta event
          print(msg)
        beats[-1] = bpm  # si más de un bpm por beat, guarda el último
    self.beats = beats


def int2note(note_int):
  note_str = notes[note_int%12]
  note_str += str(-1 + int(note_int/12))
  return note_str


mid = mido.MidiFile('data/1d9d16a9da90c090809c153754823c2b.mid')
file_type = mid.type
print('File type: {}'.format(file_type))

bpms = []
tpb = mid.ticks_per_beat

tempo_track = None
note_tracks = []
length = None

# esto sólo vale para archivos tipo 1
# con 1 canal por pista
# otros casos necesitan revisión del código
for i, track in enumerate(mid.tracks):
  if i == 0:
    tempo_track = TempoTrack(track, tpb)
    length = len(tempo_track.beats)
  else:
    note_track = Track(track, tpb, length)
    note_tracks.append(note_track)
    print(
      ', '.join([
        str(i),
        note_track.name,
        '&'.join([str(channel) for channel in note_track.channels]),
        str(note_track.ch10),
        '&'.join([str(program) for program in note_track.programs]),
        str(note_track.monophony),
        note_track.max_note_on,
        note_track.max_note_chord,
        note_track.best_key_signature,
        ', '.join(note_track.beats)
      ])
    )

# extender todo hasta el final
# revisar cuántos archivos tipo 0, y cuántos con varios canales por pista tenemos
# 

# pensaba que el end_of_track del tempo_track indicaría la longitud del tema, pero no
# una vez parseados todos los tracks, quizá debería estirarlos a todos uniformemente

# si hay más de un track por pista (archivos tipo 0, tracks con varios canales)
# es un problema seguir el tiempo, porque los delta-time se refieren al último evento

# get ticks_per_beat, constant
# since I'm interested in beats, I don't have to convert to secs


# beats = []
# beat_notes = set()
# beat_idx = 0
# for msg in track:
#   beat_idx += int(msg.time / tpb)
#   if beat_idx > len(beats):
#     beats.append(beat_notes)
#     beat_notes.clear()

  # beats[np.floor(beat)] = beats[np.floor(beat)] * notes


# que tipo de mensajes puede haber?
# program changes!
# cómo maneja la librería los running status?
# note on command with zero velocity as alias of note off

# que pasa si me encuentro con un tipo 0? ver cuantos de tipo 0 hay
# por lo pronto, los mensajes note_on y note_off tienen info del channel

# en tipo 1 hay más de un channel?

# obtener nombre del track, es información en meta, pero hay un comando que lo hace
# hay un comando is_meta

# key signature meta msg

# time signature meta event
# entiendo que no es obligatoria (es meta)
# o sea que asumimos que el denominador es 4

# de delta-time 0 a 3, inclusive, la nota queda en la primera división 1/192 de lmms
# de delta-time 4 (a 7?), en la segunda
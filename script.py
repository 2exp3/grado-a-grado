import mido
import numpy as np
from collections import Counter
import pdb
# first check file type
# if mid.file == 1, one track per instrument

notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

mid = mido.MidiFile('data/1d9d16a9da90c090809c153754823c2b.mid')
print('File type: {}'.format(mid.type))

tpb = mid.ticks_per_beat

for i, track in enumerate(mid.tracks):
  print('Track {}: {}'.format(i, track.name))

  beats = []
  chords = {}
  notes_on = set()
  beat_idx = 0

  # cuenta cuántas veces se toca (note_on) cada nota:
  note_on_count = np.zeros(len(notes), dtype=int)

  for msg in track:
    beat_idx += msg.time / tpb
    while beat_idx >= len(beats):
      beats.append(notes_on.copy())
    if msg.type == 'note_on':
      notes_on.add(msg.note)
      note_on_count[msg.note%12] += 1
    elif msg.type == 'note_off':
      notes_on.remove(msg.note)
    else:
      print(msg)
    chords[beat_idx] = notes_on.copy()
    beats[-1] |= notes_on

  monophony = len([chord for chord in chords.values() if len(chord) < 2]) / len(chords)

  # Nota mas frecuente (12 notas solamente)
  # Puede ser (i) nota tocada más veces (note_on), o
  max_note_on = ''.join([
      notes[i] for i, count in enumerate(note_on_count)
      if (count == max(note_on_count)) & (count > 0)
  ])
  # (ii) nota presente en la mayor cantidad de "acordes" (chords)
  chord_note_count = Counter([
      notes[note % 12] for chord in chords.values() for note in chord
  ])
  max_chord_note = ''.join(sorted([
      note for note, count in chord_note_count.items()
      if count == max(chord_note_count.values())
  ]))
  pdb.set_trace()


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

# obtener nombre del track, es información en meta, pero hay un comando que lo hace
# hay un comando is_meta

# key signature meta msg

# time signature meta event
# entiendo que no es obligatoria (es meta)
# o sea que asumimos que el denominador es 4

# de delta-time 0 a 3, inclusive, la nota queda en la primera división 1/192 de lmms
# de delta-time 4 (a 7?), en la segunda
import mido
import numpy as np
import pdb
# first check file type
# if mid.file == 1, one track per instrument

mid = mido.MidiFile('data/1d9d16a9da90c090809c153754823c2b.mid')
print('File type: {}'.format(mid.type))

tpb = mid.ticks_per_beat

for i, track in enumerate(mid.tracks):
  print('Track {}: {}'.format(i, track.name))

  beats = []
  chords = {}
  notes = set()
  beat_idx = 0
  for msg in track:
    beat_idx += msg.time / tpb
    while beat_idx >= len(beats):
      beats.append(notes.copy())
    if msg.type == 'note_on':
      notes.add(msg.note)
    elif msg.type == 'note_off':
      notes.remove(msg.note)
    else:
      print(msg)
    chords[beat_idx] = notes.copy()
    beats[-1] |= notes

  monophony = len([chord for chord in chords.values() if len(chord) < 2]) / len(chords)
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
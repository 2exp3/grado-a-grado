import mido
import numpy as np
# first check file type
# if mid.file == 1, one track per instrument

for i, track in enumerate(mid.tracks):
    print('Track {}: {}'.format(i, track.name))
    for msg in track:
        print(msg)

# get ticks_per_beat, constant
# since I'm interested in beats, I don't have to convert to secs

tpb = midi.ticks_per_beat

beats = mido.mid.length# array of 0 of length = number of beats in track
notes = np.full(128, False)
beat = 0
for msg in track:
	beat += msg.time / tpb
	if msg.type == 'note_on':
		notes[msg.note] = True
	elif msg.type == 'note_off':
		notes[msg.note] = False
	beats[np.floor(beat)] = beats[np.floor(beat)] * notes

#!/usr/bin/env python
# -*- coding: utf-8 -*-
import mido
import numpy as np
from collections import Counter
import csv
import pdb
# first check file type
# if mid.file == 1, one track per instrument

notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
maj_scale = [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1]
meta_ignore = [
  'midi_port',
  'end_of_track',
  'track_name',
  'lyrics',
  'marker',
  'text',
  'copyright',
  'sequencer_specific',
  'smpte_offset',
  'instrument_name',  # to-do: usar?
  'sequence_number',
  'cue_marker',
  'device_name'
]
msg_ignore = [
  'sysex',
  'pitchwheel',
  'control_change',
  'aftertouch',
  'polytouch'
]

# usa el primer track meta de cada tipo y descarta los posibles siguientes
meta_first = True

instrument_map = {}
with open('instruments.csv') as filein:
  reader = csv.DictReader(filein)
  for row in reader:
    program = int(row['program'])
    instrument = {
      'instrument': row['instrument'],
      'family': row['family']
    }
    instrument_map[program] = instrument


class NoteTrack:
  def __init__(self, num, channel, name):
    self.num = num
    self.channel = channel
    self.name = name
    self.programs = set()
    self._notes_on = set()
    # cuenta cuántas veces se toca (note_on) cada nota:
    self.note_on_count = np.zeros(len(notes), dtype=int)
    self.chords = {}  # similar a 'segments' en Echo Nest
    self.key_signatures = []  # declaradas en el archivo

  def chords2beats(self):
    beats = [set()]
    beat_idx = 0
    for beat_idx in sorted(self.chords):
      while beat_idx > len(beats):
        beats.append(beats[-1].copy())
      if beat_idx == len(beats):
        beats.append(set())
      beats[-1] |= self.chords[beat_idx]
    # cambia número de nota por string correspondiente
    self.beats = [
      ''.join([int2note(note) for note in sorted(beat)])
      for beat in beats
    ]

  def monophony(self):
    # esto debería ser sobre total de no silencios
    # porque un track puede permanecer en silencio gran parte del tema
    monophonic = [chord for chord in self.chords.values() if len(chord) == 1]
    phonic = [chord for chord in self.chords.values() if len(chord) > 0]
    monophony = len(monophonic) / len(phonic)
    return monophony

  def max_note_on(self):
    # nota tocada más veces (note_on)
    max_note_on = ''.join([
        notes[i] for i, count in enumerate(self.note_on_count)
        if count == max(self.note_on_count)
    ])
    return max_note_on

  def max_note_chord(self):
    # nota presente en la mayor cantidad de "acordes" (chords)
    chord_note_count = Counter([
        notes[note % 12] for chord in self.chords.values() for note in chord
    ])
    max_note_chord = ''.join(sorted([
        note for note, count in chord_note_count.items()
        if count == max(chord_note_count.values())
    ]))
    return max_note_chord

  def best_key_signature(self):
    # Minimización de alteraciones
    # proporción de notas fuera de la escala para cada armadura
    offscale_ratios = np.full(len(notes), None)
    for i, note in enumerate(notes):
      scale_notes = np.roll(maj_scale, -i)  # traslada el patrón de la escala
      inscale_count = (self.note_on_count * scale_notes).sum()
      total_count = self.note_on_count.sum()
      offscale_ratios[i] = 1 - inscale_count / total_count
    best_key_signature = ''.join([
        notes[i] for i, ratio in enumerate(offscale_ratios)
        if ratio == min(offscale_ratios)
    ])
    return best_key_signature


class MetaTrack:
  def __init__(self):
    self.beats = []


class MidiFile:
  def __init__(self, path):
    self.mid = mido.MidiFile(path)
    self.path = self.mid.filename
    self.type = self.mid.type
    self.tpb = self.mid.ticks_per_beat
    self.tracks = self.mid.tracks
    self.meta_tracks = {}
    self.note_tracks = []
    self.length = 0

  def read_tracks(self):
    for i, track in enumerate(self.mid.tracks):
      meta_tracks, note_tracks = parse_track(i, track, self.tpb, self.path)
      for meta_track in meta_tracks:
        if meta_track not in self.meta_tracks:
          self.meta_tracks[meta_track] = meta_tracks[meta_track]
        elif meta_first:
          # usa primer track meta de cada tipo y descarta posibles siguientes
          pass
        else:
          print("Advertencia: Meta Track '{}' ya existe!".format(meta_track))
      self.note_tracks += note_tracks
    self.norm_length()

  def norm_length(self):
    max_length = 0
    tracks = []
    tracks += [meta_track for meta_track in self.meta_tracks.values()]
    tracks += self.note_tracks
    for track in tracks:
      if len(track.beats) > max_length:
        max_length = len(track.beats)
    for track in tracks:
      while max_length > len(track.beats):
        track.beats.append(track.beats[-1])

  def stringify(self):
    import csv
    fieldnames = [
      'track_name',
      'track_num',
      'channel',
      'instruments',
      'families',
      'monophony',
      'max_note_on',
      'max_note_chord',
      'best_key_signature',
      'beats'
    ]
    with open(self.path + '.bnc', 'w') as csvfile:
      writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
      writer.writeheader()
      for name, meta_track in self.meta_tracks.items():
        row = {}
        row['track_name'] = 'Meta Track ' + name
        row['beats'] = '|'.join(str(beat) for beat in meta_track.beats)
        writer.writerow(row)
      for note_track in self.note_tracks:
        channel = note_track.channel + 1
        if channel != 10:
          # descartar note_tracks percusivos (canal 10)
          row = {}
          row['track_name'] = note_track.name
          row['track_num'] = note_track.num + 1
          row['channel'] = channel
          instruments = [
            instrument_map[program + 1] for program in note_track.programs
          ]
          row['instruments'] = '&'.join(
            [instrument['instrument'] for instrument in instruments]
          )
          row['families'] = '&'.join(
            [instrument['family'] for instrument in instruments]
          )
          row['monophony'] = note_track.monophony()
          row['max_note_on'] = note_track.max_note_on()
          row['max_note_chord'] = note_track.max_note_chord()
          row['best_key_signature'] = note_track.best_key_signature()
          row['beats'] = '|'.join(str(beat) for beat in note_track.beats)
          writer.writerow(row)


def parse_track(track_num, track, tpb, path=''):
  track_name = track.name.strip()
  meta_tracks = {}
  note_tracks = {}
  beat_idx = 0
  channel = None
  tempo = 120
  key = None
  num_den = None
  for msg in track:
    beat_idx += msg.time / tpb
    beat_idx = round(beat_idx*192)/192  # round to nearest n/192
    if msg.is_meta:
      # evento meta
      if msg.type == 'set_tempo':
        if 'tempo' not in meta_tracks:
          meta_tracks['tempo'] = MetaTrack()
        while beat_idx >= len(meta_tracks['tempo'].beats):
          meta_tracks['tempo'].beats.append(tempo)
        tempo = int(1/msg.tempo*1e6*60)
        meta_tracks['tempo'].beats[-1] = tempo
      elif msg.type == 'key_signature':
        if 'key_signature' not in meta_tracks:
          meta_tracks['key_signature'] = MetaTrack()
        while beat_idx >= len(meta_tracks['key_signature'].beats):
          meta_tracks['key_signature'].beats.append(key)  # to-do: falta major/minor
        key = msg.key
        meta_tracks['key_signature'].beats[-1] = key
      elif msg.type == 'time_signature':
        if 'time_signature' not in meta_tracks:
          meta_tracks['time_signature'] = MetaTrack()
        while beat_idx >= len(meta_tracks['time_signature'].beats):
          meta_tracks['time_signature'].beats.append(num_den)
        num_den = '{}/{}'.format(msg.numerator, msg.denominator)
        meta_tracks['time_signature'].beats[-1] = num_den
      elif msg.type == 'channel_prefix':
        channel = msg.channel
      elif msg.type in meta_ignore:
        pass
      else:
        print('Evento meta inesperado: ' + str(msg))
    elif msg.type not in msg_ignore:
      # evento midi
      channel = msg.channel
      if channel not in note_tracks:
        note_tracks[channel] = NoteTrack(track_num, channel, track_name)
      note_track = note_tracks[channel]
      programs = note_track.programs
      chords = note_track.chords
      notes_on = note_track._notes_on
      note_on_count = note_track.note_on_count
      if msg.type == 'note_on':
        if msg.velocity > 0:
          notes_on.add(msg.note)
          note_on_count[msg.note%12] += 1
        else:
          # note_on de velocidad=0 interpretado como note_off'
          if msg.note in notes_on:
            notes_on.remove(msg.note)
      elif msg.type == 'note_off':
        if msg.note in notes_on:
          notes_on.remove(msg.note)
      elif msg.type == 'program_change':
        programs.add(msg.program)
      else:
        print('Mensaje MIDI inesperado: ' + str(msg))
      chords[beat_idx] = notes_on.copy()
    else:
      # ignored events
      pass
  # descartar note_tracks sin acordes n-fónicos
  note_tracks = [
    note_track for note_track in note_tracks.values()
    if len([
      chord for chord in note_track.chords.values() if len(chord) > 0
    ]) > 0
  ]
  for i, note_track in enumerate(note_tracks):
    note_track.chords2beats()
  return meta_tracks, note_tracks


def int2note(note_int):
  note_str = notes[note_int%12]
  note_str += str(-1 + int(note_int/12))
  return note_str


def parse_file(path):
  import sys
  try:
    midi_file = MidiFile(
      str(path),
      # clip=True
    )
    if midi_file.type != 2:
      midi_file.read_tracks()
      midi_file.stringify()
    else:
      print('Error: Archivo tipo 2: ' + str(path))
  except OSError as err:
    # algunos archivos fallan con 'data byte must be in range 0..127'
    # esto es porque al menos uno de sus data bytes es > 127
    # en nuestra base de datos midi, para mensajes note_on y note_off
    # son velocity > 127, y para program_change son program > 127
    # Se puede usar MidiFile(path, clip=True), pero haría
    # program > 127 -> 127 (https://github.com/mido/mido/issues/63)
    print('OSError: {}, {}'.format(err, path))
  except ValueError as err:
    # idem data_bytes > 127 en mensajes sysex
    print('ValueError: {}, {}'.format(err, path))
  except KeyboardInterrupt:
    sys.exit()
  except as:
    print('Error inesperado, {}'.format(path))
  sys.stdout.flush()


if __name__ == '__main__':
  import argparse
  import re
  from pathlib import Path
  parser = argparse.ArgumentParser(description='Procesar archivos MIDI')
  parser.add_argument('path', help='Archivo MIDI')
  args = parser.parse_args()
  if meta_first:
    print('Atención: Usando primer track meta de cada tipo')
  if re.match(r'.*\.mid$', args.path, re.IGNORECASE):
    parse_file(args.path)
  else:
    for path in Path(args.path).glob('**/*.mid'):
      parse_file(path)
    for path in Path(args.path).glob('**/*.MID'):
      parse_file(path)

#!/usr/bin/env python
# -*- coding:utf-8 -*-

import csv
import os
import stat
import sys
import subprocess
import time


def getch():
    sys.stdin.read(1)


def mkdir(path, mode=stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH):
    if not os.path.exists(path):
        os.mkdir(path, mode)

    chmod(path, mode)


def chmod(path, mode=stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH):
    if os.path.exists(path):
        try:
            os.chmod(path, mode)
        except PermissionError as e:
            print(e)


def get_all_pathnames(dirpath, suffix=None):

    pathnames = list()

    for root, dirs, files in os.walk(dirpath, topdown=False):
        for name in files:
            if suffix is not None and not name.endswith(suffix):
                continue

            pathname = os.path.join(root, name)
            pathnames.append(pathname)

    pathnames = sorted(pathnames)

    return pathnames


def get_seconds(milliseconds):

    s = int(milliseconds / 1000)
    ms = milliseconds % 1000
    return '{}.{:03d}'.format(s, ms)


def get_start_end(period):

    start = period[0]
    end = period[1]

    if start > 0:
        start = get_seconds(start)

    end = get_seconds(end)

    return start, end


def get_ffmpeg_af(periods):

    af = ''

    for index in range(len(periods)):
        if index > 0:
            af += ', '

        start, end = get_start_end(periods[index])
        af += 'volume=enable=\'between(t,{},{})\':volume=0'.format(start, end)

    return af


def mute_audio_file(dest_file_path, audio_file_path, periods):

    af = get_ffmpeg_af(periods)

    cmd = 'ffmpeg -y -i {} -af "{}" {}'.format(
        audio_file_path, af, dest_file_path)

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    error = result.stdout
    if error and len(error) > 0:
        print(error)


def pick_out_audio_file(dest_file_path, audio_file_path, start, duration, audio_bitrate=None):

    if start > 0:
        start = get_seconds(start)

    duration = get_seconds(duration)

    if audio_bitrate and len(audio_bitrate) > 0:
        audio_bitrate = '-b:a {}'.format(audio_bitrate)

    cmd = 'ffmpeg -y -i {} -ss {} -t {} {} {}'.format(
        audio_file_path, start, duration, audio_bitrate, dest_file_path)

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    error = result.stdout
    if error and len(error) > 0:
        print(error)


def get_path_prefix(pathname):

    pos = pathname.rfind('.')

    if pos <= 0:
        return pathname

    return pathname[:pos]


def get_csv_pathname(audio_file_path):

    prefix = get_path_prefix(audio_file_path)
    return '{}.csv'.format(prefix)


def get_dest_pathname(dest_dir, audio_file_path):

    base_name = os.path.basename(audio_file_path)
    return os.path.join(dest_dir, base_name)


def mute_file(dest_dir, audio_file_path, force):

    dest_file_path = get_dest_pathname(dest_dir, audio_file_path)
    if not force and os.path.exists(dest_file_path):
        return

    periods = []

    csv_pathname = get_csv_pathname(audio_file_path)
    with open(csv_pathname, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')

        start = 0

        for cols in reader:
            if len(cols) != 3:
                return

            end = int(cols[1])
            periods.append((start, end))

            start = end + int(cols[2])

    if len(periods) == 0:
        return

    print('Muting', audio_file_path, '...')
    mute_audio_file(dest_file_path, audio_file_path, periods)


def pick_out_file(dest_dir, audio_file_path, audio_bitrate=None, force=False):

    pathname = get_dest_pathname(dest_dir, audio_file_path)
    dest_audio_dir = get_path_prefix(pathname)

    if not force and os.path.exists(dest_audio_dir):
        return

    if os.path.exists(dest_audio_dir):
        if not os.path.isdir(dest_audio_dir):
            return
    else:
        mkdir(dest_audio_dir)

    print('Picking out', audio_file_path, '...')

    csv_pathname = get_csv_pathname(audio_file_path)
    with open(csv_pathname, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')

        for cols in reader:
            if len(cols) != 3:
                return

            start = int(cols[1])
            duration = int(cols[2])

            filename = '{:08}-{:04}.mp3'.format(start, duration)
            pathname = os.path.join(dest_audio_dir, filename)

            pick_out_audio_file(pathname, audio_file_path,
                                start, duration, audio_bitrate)

    print('Picked out', audio_file_path)


def deal_with_file(dest_dir, audio_file_path, audio_bitrate, force=False):

    pick_out_file(dest_dir, audio_file_path, audio_bitrate, force)
    # mute_file(dest_dir, audio_file_path, force)


def deal_with_dir(dest_dir, dirname, audio_bitrate):

    pathnames = get_all_pathnames(dirname, '.mp3')
    for pathname in pathnames:
        deal_with_file(dest_dir, pathname, audio_bitrate)


def deal_with(dest_dir, pathname, audio_bitrate):

    if os.path.isdir(pathname):
        deal_with_dir(dest_dir, pathname, audio_bitrate)
    else:
        deal_with_file(dest_dir, pathname, audio_bitrate, force=True)


def main(argv):

    num = len(argv)

    if num < 2:
        print('Usage:\n\t', argv[0], 'AUDIO-FILE-PATH [DEST-OUTPUT-DIR]\n')
        exit()

    os.environ['TZ'] = 'Asia/Shanghai'
    time.tzset()

    pathname = os.path.realpath(argv[1])

    if num > 2:
        dest_dir = argv[2]
    else:
        dest_dir = '.'

    print('Please input audio bitrate:')
    audio_bitrate = input().strip()

    deal_with(dest_dir, pathname, audio_bitrate)


if __name__ == '__main__':
    main(sys.argv)

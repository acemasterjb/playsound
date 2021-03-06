from platform import system
from abc import ABC, abstractmethod

operating_system = system()

if operating_system == 'Windows':
    from ctypes import c_buffer, windll
    from random import random
    from time import sleep, time
    from sys import getfilesystemencoding
elif operating_system == 'Darwin':
    from AppKit import NSSound
    from Foundation import NSURL
    from time import sleep
elif operating_system == 'Linux':
    # pathname2url escapes non-URL-safe characters
    import os

    try:
        from urllib.request import pathname2url
    except ImportError:
        # python 2
        from urllib import pathname2url
    import gi

    gi.require_version('Gst', '1.0')
    from gi.repository import Gst


class PlaysoundException(Exception):
    pass

class playsoundBase(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def play(self, sound, block):
        raise NotImplemented

    @abstractmethod
    def stop(self):
        raise NotImplemented

    @abstractmethod
    def pause(self):
        raise NotImplemented

    @abstractmethod
    def resume(self, block):
        raise NotImplemented

class playsoundWin(playsoundBase):
    mcierr_duplicate_alias = 'Error 289 for command'

    def __init__(self):
        self.alias = f'playsound_alias_{id(self)}'
        self.stop_sound = False
        self.pause_sound = False

    def close_alias(self):
        """
        For cleanup purpose : will try to close an existing alias.
        """
        try:
            self.winCommand('close', self.alias)
        except:
            pass

    def stop_audio(self):
        self.winCommand('stop', self.alias)

    def pause_audio(self):
        self.winCommand('pause', self.alias)
    
    def resume_audio(self):
        self.winCommand('resume', self.alias)

    def get_duration_of_audio(self):
        duration = self.winCommand('status', self.alias, 'length')
        return duration

    def get_status(self):
        return self.winCommand('status', self.alias, 'mode').decode("utf-8")

    def winCommand(self, *command):
        buf = c_buffer(255)
        command = ' '.join(command).encode(getfilesystemencoding())
        errorCode = int(windll.winmm.mciSendStringA(command, buf, 254, 0))
        if errorCode:
            errorBuffer = c_buffer(255)
            windll.winmm.mciGetErrorStringA(errorCode, errorBuffer, 254)
            exceptionMessage = (
                '\n    Error ' + str(errorCode) + ' for command:\n'
                + command.decode() + '\n    ' + errorBuffer.value.decode())
            raise PlaysoundException(exceptionMessage)
        return buf.value
    

    
    def _manage_block(self):
        self.stop_sound = False
        self.pause_audio = False
        start_time = time()
        while True:
            sleep(0.1)
            status = self.get_status()
            if status == "stopped":
                break
        
    def play(self, sound, block=True, alias=None):
        if alias:
            self.alias = alias
        self.close_alias()
        try:
            self.winCommand(f'open "{sound}" alias', self.alias)
        except PlaysoundException as e:
            # ignore duplicate alias
            if self.mcierr_duplicate_alias not in str(e):
                raise e
        self.winCommand('play', self.alias)
        if block:
            self._manage_block()

    def stop(self):
        self.stop_sound = True
        self.stop_audio()
    
    def pause(self):
        self.pause_sound = True
        self.pause_audio()
    
    def resume(self, block=True):
        self.pause_sound = False
        if self.get_status() == 'paused':
            self.resume_audio()
            if block:
                self._manage_block()


class playsoundOSX(playsoundBase):
    def __init__(self):
        self.nssound = None
        self.stop_sound = False
        self.pause_sound = False
        self.is_playing = False

    def play(self, sound, block=True):
        '''
        Utilizes AppKit.NSSound. Tested and known to work with MP3 and WAVE on
        OS X 10.11 with Python 2.7. Probably works with anything QuickTime supports.
        Probably works on OS X 10.5 and newer. Probably works with all versions of
        Python.

        Inspired by (but not copied from) Aaron's Stack Overflow answer here:
        http://stackoverflow.com/a/34568298/901641

        I never would have tried using AppKit.NSSound without seeing his code.
        '''

        if '://' not in sound:
            if not sound.startswith('/'):
                from os import getcwd
                sound = getcwd() + '/' + sound
            sound = 'file://' + sound
        url = NSURL.URLWithString_(sound)
        self.nssound = NSSound.alloc().initWithContentsOfURL_byReference_(url, True)
        if not self.nssound:
            raise IOError('Unable to load sound named: ' + sound)
        self.is_playing = True
        self.nssound.play()

        if block:
            sleep(self.nssound.duration())

    def stop(self):
        self.stop_sound = True
        if self.nssound and self.is_playing:
            self.nssound.stop()
        else:
            pass

    def resume(self, block):
        if self.nssound and self.paused:
            self.paused = False
            self.nssound.resume()
            if block:
                sleep(self.nssound.duration())
        else:
            pass

    def pause(self):
        self.pause_sound = True
        if self.nssound:
            self.nssound.pause()
        else:
            pass
        
class playsoundNix(playsoundBase):
    def play(self, sound, block=True):
        """Play a sound using GStreamer.

        Inspired by this:
        https://gstreamer.freedesktop.org/documentation/tutorials/playback/playbin-usage.html
        """
        if not block:
            raise NotImplementedError(
                "block=False cannot be used on this platform yet")

        Gst.init(None)

        playbin = Gst.ElementFactory.make('playbin', 'playbin')
        if sound.startswith(('http://', 'https://')):
            playbin.props.uri = sound
        else:
            playbin.props.uri = 'file://' + pathname2url(
                os.path.abspath(sound))

        set_result = playbin.set_state(Gst.State.PLAYING)
        if set_result != Gst.StateChangeReturn.ASYNC:
            raise PlaysoundException(
                "playbin.set_state returned " + repr(set_result))

        # FIXME: use some other bus method than poll() with block=False
        # https://lazka.github.io/pgi-docs/#Gst-1.0/classes/Bus.html
        bus = playbin.get_bus()
        bus.poll(Gst.MessageType.EOS, Gst.CLOCK_TIME_NONE)
        playbin.set_state(Gst.State.NULL)

    def stop(self):
        raise NotImplemented


if operating_system == 'Windows':
    playsound = playsoundWin
elif operating_system == 'Darwin':
    playsound = playsoundOSX
elif operating_system == 'Linux':
    playsound = playsoundNix

del operating_system

#!/usr/bin/env python
# encoding: utf-8
# © 2015 Chloé Tigre Rouge Desoutter
# MIT license - See LICENSE

"""IRCbot in Python with plug-in system
Port of the Ruby version
"""

import socket
import re
import sys

from threading import Thread
from time import sleep

"""
This class implements an IRC bot that connects to a server, performs basic 
connection and stuff and then allows you to feed plug-ins with info  about the 
received PRIVMSG so you can design whatever you like around it.
"""
class IRCBot:
  _socket = None
  _connected = False

  _callbacks = []
  _recvcallbacks = []
  _privmsgcallbacks = []

  """ self-explanatory. ipv4 only for the moment """
  def connect(self, server, port):
    self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    addr = (server, port)
    self._socket.connect(addr)
    self.run_connected()

  """ self-explanatory """
  def disconnect(self):
    self._socket_file.close()
    self._socket.shutdown(socket.SHUT_RDWR)
    self._socket.close()
    self._connected = False

  """ work after having created the socket """
  def run_connected(self):
    self._socket_file = self._socket.makefile('r')
    self._connected = True
    self.add_callback(lambda: self.connect_user("IRCbotpy", "An IRCbotpy user"))
    self.add_callback(lambda: self.join_channel_sync("#bottest", "Hello, world"))
    self.start_threads()

  """ send message through socket """
  def send_message(self, message):
    print("Sending",message)
    return self._socket.send(message+"\r\n")

  """ add a callback independent from the messages received, like an urgent
  callback of any sort. 
  called once then removed from the queue
  """
  def add_callback(self, callback):
    self._callbacks.insert(0, callback)

  """ add a callback that is called when any server message is received that
  matches the regex. This callback takes no parameter. This is a one-shot
  callback and it will need to be added back to the queue if you want it
  to run again.
  """
  def add_regex_callback(self, regex, callback):
    self._recvcallbacks.insert(0, (regex, callback))

  """ add a callback that is triggered when a message matches it.
  These callbacks stay in the list of callbacks and will not get automatically
  removed """
  def add_privmsg_callback(self, regex, callback):
    self._privmsgcallbacks.insert(0, (regex, callback))

  """ start threads """
  def start_threads(self):
    self._irc_thread = Thread(target = self.irc_loop)
    self._execution_thread = Thread(target = self.poll_exec_queue)
    self._irc_thread.start()
    self._execution_thread.start()
    while (self._execution_thread.isAlive() or self._irc_thread.isAlive()) and self._connected:
      self._execution_thread.join(1)
      self._irc_thread.join(1)
    print("out of start_threads")

  """ main IRC loop. Gets messages, puts callbacks in the execution queue. """
  def irc_loop(self):
    line = self._socket_file.readline().rstrip()
    reg_privmsg = re.compile(r"^:(\S+)!(\S+) PRIVMSG (\S+) :(.*)$")
    while line!='' and self._connected:
      # handle recv callbacks
      callbacks = [ x for x in self._recvcallbacks if (x[0].match(line)) is not None ]
      for i in callbacks:
        i[1]()
      match = reg_privmsg.match(line)
      if (match is not None):
        user = match.group(1)
        host = match.group(2)
        dest = match.group(3)
        mesg = match.group(4)
        callbacks = [ x for x in self._privmsgcallbacks 
          if x[0].match(mesg) is not None ]
        for c in callbacks:
          self.add_callback(lambda: c[1](user, host, dest, mesg))
      line = self._socket_file.readline().rstrip()
      sleep(0.1)

  """ the callback runner """
  def poll_exec_queue(self):
    while self._connected:
      while len(self._callbacks) > 0:
        self._callbacks.pop()()
      sleep(1)

  """ utility IRC functions """
  def connect_user(self, nickname, description):
    self.send_message("NICK %s" % (nickname))
    sleep(1)
    self.send_message("USER %s 0 * :%s" % (nickname, description))

  def join_channel(self, channel):
    self._channel = channel
    self.send_message("JOIN %s" % (channel))

  def join_channel_sync(self, channel, message):
    def _jc():
      print("have connected")
      self.send_chat(channel, message)
    reg = re.compile(".*JOIN %s$" % (channel))
    self.add_regex_callback(reg, _jc)
    self.join_channel(channel)

  def send_chat(self, destination, contents):
    contents = contents.rstrip()
    for line in contents.split('\n'):
      line = line.rstrip()
      self.send_message("PRIVMSG %s :%s" % (destination, line))

if (__name__ == '__main__'):
  print("Invoked")
  c = IRCBot()
  def exampleexitcallback(user, host, dest, mesg):
    if (user == 'ChloeD'):
      print("Oh, hello ChloeD")
      c.send_chat("#bottest", "I'm leaving now")
      c.disconnect()
      sys.exit(0)
  def fortunecallback(user, host, dest, mesg):
    from subprocess import PIPE, Popen
    txt = Popen("fortune", stdout=PIPE).stdout.read()
    c.send_chat(dest, txt)
    
  c.add_privmsg_callback(re.compile("!exit"), exampleexitcallback)
  c.add_privmsg_callback(re.compile("!fortune"), fortunecallback)
  c.connect("irc.freenode.net", 6667)

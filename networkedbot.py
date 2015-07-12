#!/usr/bin/env python3

from ircbot import IRCBot
from threading import Thread
import uuid
import re

"""
IRC Bot able to sync with other peers and to know them. Then it can be extended
to support stuff like coordinated searches and so on
"""
class Botsync:
  started = False
  peers = set()
  unique_id = None
  advertised = False

  """TODO: fetch the channel from the irc connector"""
  def __init__(self, irc, channel):
    self.unique_id = str(uuid.uuid4())
    self._irc = irc
    self._channel = channel
  
  """schedule a start at the end of MOTD (hackish Freenodeism)"""
  def schedule_start(self):
    self._irc.add_regex_callback(re.compile(".*MOTD*"), self._start)

  """announce oneself to other bots, many times if needed"""
  def announce(self, dest=None):
    if dest is None:
      dest = self._channel
    self._irc.send_chat(dest, "BOT:"+self.unique_id)

  """say hello first time"""
  def advertise(self):
    if not self.advertised:
      self._irc.send_chat(self._channel, "ADV:"+self.unique_id)
      self.advertised = True
  
  """handle other peer announcements"""
  def parse_announce(self, user, host, dest, mesg):
    self.peers.add((user, mesg[4:]))
    print(self._irc._nick, "New peer!", "parse_announce", self.peers)

  """handle other peer announcements and announce oneself"""
  def parse_advertised(self, user, host, dest, mesg):
    self.peers.add((user, mesg[4:]))
    print(self._irc._nick, "New peer!", "parse_advertised", self.peers)
    self.announce(user)

  def tell_who_you_know(self, user, host, dest, mesg):
    self._irc.send_chat(dest, "I know " + ", ".join([ x[0] for x in self.peers ]))
    
  def _start(self):
    self._irc.join_channel_then_cb(self._channel, self.advertise)
    self._irc.add_privmsg_callback(re.compile("ADV:\S+"), self.parse_advertised)
    self._irc.add_privmsg_callback(re.compile("BOT:\S+"), self.parse_announce)
    self._irc.add_privmsg_callback(re.compile("!whoyouknow"), self.tell_who_you_know)

if __name__ == '__main__':
  import sys
  c = IRCBot(sys.argv[1])
  def exampleexitcallback(user, host, dest, mesg):
    if (user == 'ChloeD'):
      print("Oh, hello ChloeD")
      c.send_chat("#bottest", "I'm leaving now")
      c.disconnect()
      sys.exit(0)
  c.add_privmsg_callback(re.compile("!exit"), exampleexitcallback)
  bot = Botsync(c, "#bottest")
  t1 = Thread(target=lambda:c.connect("irc.freenode.net", 6667, "#bottest"))
  t2 = Thread(target=bot.schedule_start)
  t1.start()
  t2.start()
  [ x.join() for x in [ t1, t2 ] ]

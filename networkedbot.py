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
  recved_jobs_pending = []
  recved_jobs_hired = []
  emitted_jobs_sentout = []
  emitted_jobs_accepted = []

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

    
  """
  as worker. handle a job proposal: send a CLAIM request to the original author
  to claim the job. If he agrees, then we will perform the job otherwise we
  will just discard it
  """
  def handle_job_proposal(self, user, host, dest, mesg):
    _, jobid, parameters = mesg.split(sep=':', maxsplit=3)
    print(self._irc._nick,"handle_job_proposal",(jobid,parameters))
    self.recved_jobs_pending.append((jobid, parameters))
    self._irc.send_chat(user, "CLAIM:"+jobid)

  """as job offerer. handle a peer's claim for a job"""
  def handle_job_claim(self, user, host, dest, mesg):
    _, jobid = mesg.split(sep=':', maxsplit=2)
    if len([ x for x in self.emitted_jobs_accepted if x[0] == jobid])>0:
      self._irc.send_chat(user, 'NOTHANKS:'+jobid)
      print(self._irc._nick,"handle_job_claim",jobid,"NOTHANKS")
    else:
      self.emitted_jobs_accepted.append((jobid,[x for x in self.peers if x[0]==user][0]))
      self._irc.send_chat(user, 'THANKS:'+jobid)
      print(self._irc._nick,"handle_job_claim",jobid,"THANKS")

  def handle_hire_accepted(self, user, host, dest, mesg):
    _, jobid = mesg.split(sep=':', maxsplit=2)
    print(self._irc._nick,"hire_accepted",jobid)
    self.recved_jobs_hired.append([x for x in self.recved_jobs_pending if x[0] == jobid][0])
    try:
      self.recved_jobs_pending.remove([x for x in self.recved_jobs_pending if x[0] == jobid][0])
    except ValueError:
      pass

  def handle_hire_refused(self, user, host, dest, mesg):
    _, jobid = mesg.split(sep=':', maxsplit=2)
    print(self._irc._nick,"hire_refused",jobid)
    try:
      self.recved_jobs_pending.remove([x for x in self.recved_jobs_pending if x[0] == jobid][0])
    except ValueError:
      pass


  """tell who I know as peers"""
  def tell_who_you_know(self, user, host, dest, mesg):
    self._irc.send_chat(dest, "I know " + ", ".join([ x[0] for x in self.peers ]))

  """Report jobs"""
  def report_my_jobs(self, user, host, dest, mesg):
    self._irc.send_chat(dest, "Emitted jobs sentout: " + ", ".join([ x[0] for x in self.emitted_jobs_sentout ]))
    self._irc.send_chat(dest, "Emitted jobs accepted: " + ", ".join([ x[0] for x in self.emitted_jobs_accepted ]))
    self._irc.send_chat(dest, "Received jobs pending: " + ", ".join([ x[0] for x in self.recved_jobs_pending ]))
    self._irc.send_chat(dest, "Received jobs hired: " + ", ".join([ x[0] for x in self.recved_jobs_hired ]))

  """Send a job offer to the peers"""
  def emit_a_job(self, user, host, dest, mesg):
    _, jobid, parameters = mesg.split(sep=':', maxsplit=3)
    job = (jobid, parameters)
    if len([ x for x in self.emitted_jobs_sentout if x[0]==jobid])==0:
      self.emitted_jobs_sentout.append(job)
      self._irc.send_chat(self._channel,"JOB:%s:%s" % job)

  """handle messages"""
  def _start(self):
    # peer recognition
    self._irc.add_privmsg_callback(re.compile("^ADV:\S+"), self.parse_advertised)
    self._irc.add_privmsg_callback(re.compile("^BOT:\S+"), self.parse_announce)
    # handle a job proposal
    self._irc.add_privmsg_callback(re.compile("^JOB:([^:]+):(.*)+"), self.handle_job_proposal)
    # handle a job claim
    self._irc.add_privmsg_callback(re.compile("^CLAIM:([^:]+)"), self.handle_job_claim)
    # handle (non-)hiring
    self._irc.add_privmsg_callback(re.compile("^THANKS:([^:]+)"), self.handle_hire_accepted)
    self._irc.add_privmsg_callback(re.compile("^NOTHANKS:([^:]+)"), self.handle_hire_refused)


    # some (testish) triggers
    self._irc.add_privmsg_callback(re.compile("!whoyouknow"), self.tell_who_you_know)
    self._irc.add_privmsg_callback(re.compile("!jobs"), self.report_my_jobs)
    self._irc.add_privmsg_callback(re.compile("!emitjob:([^:]+):(.*)"), self.emit_a_job)
    
    self._irc.join_channel_then_cb(self._channel, self.advertise)

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

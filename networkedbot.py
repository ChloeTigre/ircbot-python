#!/usr/bin/env python3

from ircbot import IRCBot
from threading import Thread
from concurrent import futures
from time import sleep

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
  recved_jobs_working = []

  emitted_jobs_sentout = []
  emitted_jobs_accepted = []

  jobbers = set()
  known_results = dict()

  """TODO: fetch the channel from the irc connector"""
  def __init__(self, irc, channel, capacity = 3):
    self.unique_id = str(uuid.uuid4())
    self._irc = irc
    self._channel = channel
    self._capacity = capacity
  
  """Add a work executor"""
  def add_work_executor(self, cutor):
    self.jobbers.add(cutor)

  """Dispatch job"""
  def dispatch_job(self):
    with futures.ThreadPoolExecutor(max_workers=3) as executor:
      promises = {}
      for t in self.recved_jobs_hired:
        for jobber in self.jobbers:
          if jobber.would_accept(t[1]):
            self.recved_jobs_hired.remove(t)
            self.recved_jobs_working.append((t,jobber))
            promises[executor.submit(jobber.perform, t[1])] = t
      for future in futures.as_completed(promises):
        job = promises[future]
        r = future.result()
        self._irc.send_chat(self._channel, "JOBRESULT:%s:%s"%(t[0],r))
        self.known_results[t[0]] = r

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

  """as worker. handle a job proposal: send a CLAIM request to the original 
  author to claim the job. If he agrees, then we will perform the job otherwise
  we will just discard it"""
  def handle_job_proposal(self, user, host, dest, mesg):
    _, jobid, parameters = mesg.split(sep=':', maxsplit=3)
    print(self._irc._nick,"handle_job_proposal",(jobid,parameters))
    if len(self.recved_jobs_pending) < self._capacity:
      self.recved_jobs_pending.append((jobid, parameters))
      self._irc.send_chat(user, "CLAIM:"+jobid)

  """handle job result"""
  def handle_job_result(self, user, host, dest, mesg):
    _, jobid, result = mesg.split(sep=':', maxsplit=3)
    self.known_results[jobid] = result

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
    Thread(target=self.dispatch_job).start()
    # no need to join that thread, it's running in another thread that's joined

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

  """Send a result (trigger parameter is a job id)"""
  def get_known_result(self, user, host, dest, mesg):
    _, wantedkey = mesg.split(sep=':', maxsplit=2)
    if wantedkey in self.known_results:
      self._irc.send_chat(user, "RESULT:%s:%s" % (wantedkey, self.known_results[wantedkey]))
      self._irc.send_chat(dest, "RESULT:%s:%s" % (wantedkey, self.known_results[wantedkey]))
    else:
      self._irc.send_chat(user, "UNKNOWN_RESULT:%s" % (wantedkey))
      self._irc.send_chat(dest, "UNKNOWN_RESULT:%s" % (wantedkey))

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
    # handle a job result announcement
    self._irc.add_privmsg_callback(re.compile("^JOBRESULT:([^:]+):(.*)"), self.handle_job_result)


    # some triggers
    self._irc.add_privmsg_callback(re.compile("!whoyouknow"), self.tell_who_you_know)
    self._irc.add_privmsg_callback(re.compile("!jobs"), self.report_my_jobs)
    self._irc.add_privmsg_callback(re.compile("!emitjob:([^:]+):(.*)"), self.emit_a_job)
    self._irc.add_privmsg_callback(re.compile("!getresult:(.*)"), self.get_known_result)
    
    # start the real thing
    self._irc.join_channel_then_cb(self._channel, self.advertise)

"""this is a stupid job planner that computes badly basic stuff such as powers,
after sleeping for a while"""
class StupidMathsWorker:
  def would_accept(self, parameters):
    split = parameters.split(',')
    if split[0]=="pow" or split[0]=="fibonacci":
      return True
    return False

  def perform(self, parameters):
    split = parameters.split(',')
    sleep(5)
    if split[0]=="pow":
      f = float(split[1])
      e = float(split[2])
      return f**e    
    if split[0]=="fibonacci":
      a = [0, 1]
      tgt = int(split[1])
      v = 0
      while tgt >= 2:
        v = a[0] + a[1]
        a[0] = a[1]
        a[1] = v
        tgt -= 1
      return v


if __name__ == '__main__':
  import sys
  c = IRCBot(sys.argv[1], verbosity=True)
  def exampleexitcallback(user, host, dest, mesg):
    if (user == 'ChloeD'):
      print("Oh, hello ChloeD")
      c.send_chat("#bottest", "I'm leaving now")
      c.disconnect()
      sys.exit(0)
  c.add_privmsg_callback(re.compile("!exit"), exampleexitcallback)
  bot = Botsync(c, "#bottest")
  bot.add_work_executor(StupidMathsWorker())
  t1 = Thread(target=lambda:c.connect("irc.freenode.net", 6667, "#bottest"))
  t2 = Thread(target=bot.schedule_start)
  t1.start()
  t2.start()
  [ x.join() for x in [ t1, t2 ] ]

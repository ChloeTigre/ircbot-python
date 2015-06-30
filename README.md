IRCBot-py
=========

Basically, this aims to be a Python port of my Ruby IRC bot.
This is a toy project in python that I intend to use for stuff like
system monitoring and other noise-making on IRC.

How to add functionalities
==========================

Implement functions with the following prototype:
  def fn(nickname, hostname, destination, message)

Write a regex matching the PRIVMSG you want it to match.

Call add_privmsg_callback.

State
=====

For now not at all ready for any production. Still lacks proper facilities
for external manipulation, configuration files, an interactive prompt,
a standardized way to load plug-ins, multi-server support (though one process
per server could od), getting some constants out of the code, proper disconnect.

Still pushing it so people can derivate from it if they dare.

License
=======

As usual, MIT license.

Authors
=======

Chloé "Tigre Rouge" Desoutter <chloe@tigres-rouges.net>


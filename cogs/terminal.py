from discord.ext import commands
from subprocess import Popen, CalledProcessError, PIPE, STDOUT
from os.path import splitext, exists
from os import makedirs, getcwd, chdir, listdir, replace
from getpass import getuser
from platform import uname
from re import sub
from random import randint
import json

class DataIO():

    def save_json(self, filename, data):
        """Atomically saves json file"""
        rnd = randint(1000, 9999)
        path, ext = splitext(filename)
        tmp_file = "{}-{}.tmp".format(path, rnd)
        self._save_json(tmp_file, data)
        try:
            self._read_json(tmp_file)
        except json.decoder.JSONDecodeError:
            self.logger.exception("Attempted to write file {} but JSON "
                                  "integrity check on tmp file has failed. "
                                  "The original file is unaltered."
                                  "".format(filename))
            return False
        replace(tmp_file, filename)
        return True

    def load_json(self, filename):
        """Loads json file"""
        return self._read_json(filename)

    def is_valid_json(self, filename):
        """Verifies if json file exists / is readable"""
        try:
            self._read_json(filename)
            return True
        except FileNotFoundError:
            return False
        except json.decoder.JSONDecodeError:
            return False

    def _read_json(self, filename):
        with open(filename, encoding='utf-8', mode="r") as f:
            data = json.load(f)
        return data

    def _save_json(self, filename, data):
        with open(filename, encoding='utf-8', mode="w") as f:
            json.dump(data, f, indent=4,sort_keys=True,
                separators=(',',' : '))
        return data

dataIO = DataIO()

def escape_mass_mentions(text):
    return escape(text, mass_mentions=True)

def escape(text, *, mass_mentions=False, formatting=False):
    if mass_mentions:
        text = text.replace("@everyone", "@\u200beveryone")
        text = text.replace("@here", "@\u200bhere")
    if formatting:
        text = (text.replace("`", "\\`")
                    .replace("*", "\\*")
                    .replace("_", "\\_")
                    .replace("~", "\\~"))
    return text
	
def box(text, lang=""):
    ret = "```{}\n{}\n```".format(lang, text)
    return ret
    
def pagify(text, delims=["\n"], *, escape=True, shorten_by=8,
           page_length=2000):
    """DOES NOT RESPECT MARKDOWN BOXES OR INLINE CODE"""
    in_text = text
    if escape:
        num_mentions = text.count("@here") + text.count("@everyone")
        shorten_by += num_mentions
    page_length -= shorten_by
    while len(in_text) > page_length:
        closest_delim = max([in_text.rfind(d, 0, page_length)
                             for d in delims])
        closest_delim = closest_delim if closest_delim != -1 else page_length
        if escape:
            to_send = escape_mass_mentions(in_text[:closest_delim])
        else:
            to_send = in_text[:closest_delim]
        yield to_send
        in_text = in_text[closest_delim:]

    if escape:
        yield escape_mass_mentions(in_text)
    else:
        yield in_text
    
class Terminal:
    """Repl like Terminal in discord"""

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json('settings/terminal/settings.json') # Initial load of values making sure they are read right when the cog loads
        self.prefix = self.settings['prefix']
        self.os = self.settings['os']
        self.enabled = self.settings['enabled']
        self.sessions = []

    async def send_cmd_help(self, ctx):
        if ctx.invoked_subcommand:
            pages = self.bot.formatter.format_help_for(ctx, ctx.invoked_subcommand)
            for page in pages:
                await self.bot.send_message(ctx.message.channel, page)
        else:
            pages = self.bot.formatter.format_help_for(ctx, ctx.command)
            for page in pages:
                await self.bot.send_message(ctx.message.channel, page)

    @commands.command(pass_context=True)
    async def cmd(self, ctx):

        if ctx.message.channel.id in self.sessions:
            await self.bot.say('Already running a Terminal session in this channel. Exit it with `exit()`')
            return

        # Rereading the values that were already read in __init__ to ensure its always up to date
        try:
            self.settings = dataIO.load_json('settings/terminal/settings.json')
        except:
            # Pretend its the worst case and reset the settings
            check_folder()
            check_file()
            self.settings = dataIO.load_json('settings/terminal/settings.json')

        self.prefix = self.settings['prefix']
        self.cc = self.settings['cc']
        self.os = self.settings['os']

        self.sessions.append(ctx.message.channel.id)
        await self.bot.say('Enter commands after {} to execute them. `exit()` to exit.'.format(self.prefix.replace("`", "\\`")))


    @commands.group(pass_context=True)
    async def cmdsettings(self, ctx):
        """Settings for Terminal"""
        if ctx.invoked_subcommand is None:
            await self.send_cmd_help(ctx)

    @cmdsettings.command(name="prefix", pass_context=True)
    async def _prefix(self, ctx, prefix:str=None):
        """Set the prefix for the Terminal"""
        
        if prefix == None:
            await self.send_cmd_help(ctx)
            await self.bot.say(box('Current prefix: ' + self.prefix))
            return
            
        self.prefix = prefix
        self.settings['prefix'] = self.prefix
        dataIO.save_json('settings/terminal/settings.json', self.settings)
        await self.bot.say('Changed prefix to {} '.format(self.prefix.replace("`", "\\`")))

    async def on_message(self, message): # This is where the magic starts
        
        if self.bot.user.id != message.author.id:
            return
                
        if message.channel.id in self.sessions and self.enabled: # Check if the current channel is the one cmd got started in

            #TODO:
            #  Whitelist & Blacklists that cant be modified by red

            def check(m):
                if m.content.strip().lower() == "more":
                    return True

            if not self.prefix: # Making little 1337 Hax0rs not fuck this command up
                check_folder()
                check_file()

            if message.content.startswith(self.prefix) or message.content.startswith('debugprefixcmd'):
                command = message.content.split(self.prefix)[1]
                # check if the message starts with the command prefix

                if not command: # if you have entered nothing it will just ignore
                    return


                if command == 'exit()':  # commands used for quiting cmd, same as for repl
                    await self.bot.send_message(message.channel, 'Exiting.')
                    self.sessions.remove(message.channel.id)
                    return

                if command.lower().find("apt-get install") != -1 and command.lower().find("-y") == -1:
                    command = "{} -y".format(command) # forces apt-get to not ask for a prompt

                if command in self.cc:
                    command = self.cc[command]

                if command.startswith('cd ') and command.split('cd ')[1]:
                    path = command.split('cd ')[1]
                    try:
                        chdir(path)
                        return
                    except:
                        if path in listdir() or path.startswith('/'):
                            shell = 'cd: {}: Permission denied'.format(path)
                        else:
                            shell = 'cd: {}: No such file or directory'.format(path)
                else:
                    try:
                        output = Popen(command, shell=True, stdout=PIPE, stderr=STDOUT).communicate()[0] # This is what proccesses the commands and returns their output
                        error = False
                    except CalledProcessError as e:
                        output = e.output
                        error = True

                    shell = output.decode('utf_8')

                if shell == "" and not error: # check if the previous run command is giving output and is not a error
                    return

                shell = sub('/bin/sh: .: ', '', shell)
                if "\n" in shell[:-2]:
                    shell = '\n' + shell

                os = uname()[0].lower()

                if os.lower() in self.os:
                    path = getcwd()
                    username = getuser()
                    system = uname()[1]
                    user = self.os[os.lower()].format(user=username, system=system, path=path)
                else:
                    path = getcwd()
                    username = getuser()
                    system = uname()[1]
                    user = self.os['linux'].format(user=username, system=system, path=path)

                result = list(pagify(user + shell, shorten_by=12))

                for x, output in enumerate(result):
                    if x % 2 == 0 and x != 0:
                        # TODO
                        #  Change it up to a reaction based system like repl
                        #  change up certain things. For example making a print template in the settings print character number not page number

                        note = await self.bot.send_message(message.channel, 'There are still {} pages left.\nType `more` to continue.'.format(len(result) - (x+1)))
                        msg = await self.bot.wait_for_message(author=message.author,
                                                      channel=message.channel,
                                                      check=check,
                                                      timeout=12)
                        if msg == None:
                            try:
                                await self.bot.delete_message(note)
                            except:
                                pass
                            finally:
                                break

                    await self.bot.send_message(message.channel, box(output, 'Bash'))


def check_folder():
    if not exists("settings/terminal"):
        print("[Terminal]Creating settings/terminal folder...")
        makedirs("settings/terminal")


def check_file():
    jdict = {
        "prefix":">",
        "cc":{'test' : 'printf "Hello.\nThis is a custom command made using the magic of ~~unicorn poop~~ python.\nLook into /settings/terminal"'},
        "os":{
            'windows':'{path}>',
            'linux':'{user}@{system}:{path} $ '
            },
        "enabled":True
        }

    if not dataIO.is_valid_json("settings/terminal/settings.json"):
        print("[Terminal]Creating default settings.json...")
        dataIO.save_json("settings/terminal/settings.json", jdict)

def setup(bot):
    check_folder()
    check_file()
    bot.add_cog(Terminal(bot))

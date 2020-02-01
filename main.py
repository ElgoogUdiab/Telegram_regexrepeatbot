from telegram.ext import Updater
import json
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import requests
import re
import rstr
import datetime
import time
from copy import copy

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    with open("token") as f:
        token = f.readline().strip()
except:
    print("No token! Create file named \"token\" under the same directory with main.py!")
    exit(1)
try:
    with open("pattern.json") as f:
        patterns = json.load(f)
except:
    patterns = {}

updater = Updater(token=token, use_context=True)
dispatcher = updater.dispatcher

url = "https://{lang}.wikipedia.org/wiki/Special:Random"

def update_pattern(chat_id, patt=None):
    global patterns
    if not str(chat_id) in patterns:
        patterns.update({str(chat_id): {"enabled": True, "patterns": {}}})
    if not "enabled" in patterns[str(chat_id)]:
        patterns[str(chat_id)].update({"enabled": True})
    if patt != None:
        name = patt.pop("name")
        patterns[str(chat_id)]["patterns"].update({name: patt})
    with open("pattern.json", "w") as f:
        json.dump(patterns, f)

def start(update, context):
    # context.bot.send_message(chat_id=update.effective_chat.id, text=str(update.effective_chat.id))
    update_pattern(str(update.effective_chat.id), None)
start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

PATTERN, RESPONSE_REGEX, RESPONSE_PATTERN = range(3)
def add_pattern(update, context):
    if len(context.args) != 1:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /add <Rule name>")
        return ConversationHandler.END
    name = context.args[0]
    if name in patterns[str(update.effective_chat.id)]["patterns"]:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Rule with same name exists!")
        return ConversationHandler.END
    data = context.user_data
    data.update({"name": name})
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! Setting rule {name}.\nNow give me the pattern.\
    \nRemember to add ^ and $ when necessary.\
    \nNote: You can cancel at any time by typing /cancel")
    return PATTERN
def define_pattern(update, context):
    pattern = update.message.text
    try:
        re.compile(pattern)
    except re.error:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Seems not a valid regex. Please try again.")
        return PATTERN
    if re.search(pattern, ""):
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Seems that this pattern can match any string.\nPlease check your pattern regex and try again.")
        return PATTERN
    data = context.user_data
    data.update({"pattern": pattern})
    keyboard = [
        [InlineKeyboardButton("Yes", callback_data="Yes"),
         InlineKeyboardButton("No", callback_data="No")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! The pattern is {pattern}.\nWould you please tell me whether the response is a regex or not?", reply_markup=reply_markup)
    return RESPONSE_REGEX
def define_whether_regex_false(update, context):
    data = context.user_data
    data.update({"is_regex": False})
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! The reply text is NOT a regex.\nNow give the response.")
    return RESPONSE_PATTERN
def define_whether_regex_true(update, context):
    data = context.user_data
    data.update({"is_regex": True})
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! The reply text is a regex.\nNow give the response.")
    return RESPONSE_PATTERN
def define_response(update, context):
    data = context.user_data
    response = update.message.text
    if data["is_regex"]:
        try:
            rstr.xeger(response)
        except:
            context.bot.send_message(chat_id=update.effective_chat.id, text=f"Unable to generate string from the given regex!\nPlease try another regex.")
            return RESPONSE_PATTERN
    data.update({"response": response})
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! The reply text is {response}.\nThis rule should be functioning now.")
    update_pattern(update.effective_chat.id, copy(data))
    data.clear()
    return ConversationHandler.END

def cancel(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! Canceled")
    data = context.user_data
    data.clear()
    return ConversationHandler.END

add_pattern_handler = ConversationHandler(
    entry_points=[CommandHandler('add', add_pattern, pass_args=True)],
    states = {
        PATTERN: [MessageHandler(Filters.text, define_pattern)],
        RESPONSE_REGEX: [
            CallbackQueryHandler(define_whether_regex_true, pattern=r"^Yes$"),
            CallbackQueryHandler(define_whether_regex_false, pattern=r"^No$")
        ],
        RESPONSE_PATTERN: [MessageHandler(Filters.text, define_response)]
    },
    fallbacks = [CommandHandler('cancel', cancel, pass_args=True)]
)
dispatcher.add_handler(add_pattern_handler)

def del_pattern(update, context):
    if len(context.args)!=1:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Usage: /del <Rule name>")
        return
    name = context.args[0]
    if not name in patterns[str(update.effective_chat.id)]["patterns"]:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Rule not found!")
        return
    patterns[str(update.effective_chat.id)]["patterns"].pop(name)
    update_pattern(str(update.effective_chat.id))
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"Rule deleted.")
del_pattern_handler = CommandHandler('del', del_pattern, pass_args=True)
dispatcher.add_handler(del_pattern_handler)


def show_patterns(update, context):
    try:
        pattern = patterns[str(update.effective_chat.id)]["patterns"]
    except:
        pattern = {}
    if not pattern:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"No rule here.")
    else:
        out_str = "Here are the rules:\n"
        out_str += "\n".join([f"{name}: {patt['pattern']} -> {patt['response']}" for name, patt in pattern.items()])
        context.bot.send_message(chat_id=update.effective_chat.id, text=out_str)
show_pattern_handler = CommandHandler('show', show_patterns)
dispatcher.add_handler(show_pattern_handler)


def processing(update, context):
    update_pattern(str(update.effective_chat.id))
    if patterns[str(update.effective_chat.id)]["enabled"]:
        message = update.message.text
        for name, pattern in patterns[str(update.effective_chat.id)]["patterns"].items():
            if re.search(pattern["pattern"], message):
                logger.info("Update \"%s\" matches rule \"%s\": %s", message, name, str(pattern))
                if pattern["is_regex"]:
                    response = rstr.xeger(pattern["response"])
                else:
                    response = pattern["response"]
                context.bot.send_message(chat_id=update.effective_chat.id, text=response)
                break
    return
echo_handler = MessageHandler(Filters.text, processing)
dispatcher.add_handler(echo_handler)

def disable(update, context):
    timer = None
    if len(context.args) == 1:
        try:
            timer = float(context.args[0])
            if timer < 0:
                context.bot.send_message(chat_id=update.effective_chat.id, text=f"Negative timer make no sense.")
                return
        except:
            context.bot.send_message(chat_id=update.effective_chat.id, text=f"Usage: /disable [Seconds]")
            return
    elif len(context.args) > 1:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Usage: /disable [Seconds]")
        return
    patterns[str(update.effective_chat.id)]["enabled"]=False
    if timer:
        if timer > 3600:
            reply = f"The bot is temporarily disabled for {round(timer/3600, 2)} hours."
        elif timer > 60:
            reply = f"The bot is temporarily disabled for {round(timer/60, 2)} minutes."
        else:
            reply = f"The bot is temporarily disabled for {timer} seconds."
        reply+= f"\nAnd will be re-enabled at {datetime.datetime.fromtimestamp(int(time.time()+timer))}."
        if 'job' in context.chat_data:
            old_job = context.chat_data['job']
            old_job.schedule_removal()
        new_job = context.job_queue.run_once(re_enable, timer, context={"chat_id": update.effective_chat.id, "target": True})
    else:
        reply = "The bot is disabled in this chat."
    update_pattern(str(update.effective_chat.id))
    context.bot.send_message(chat_id=update.effective_chat.id, text=reply)

    
disable_handler = CommandHandler('disable', disable, pass_args=True)
dispatcher.add_handler(disable_handler)
def enable(update, context):
    timer = None
    if len(context.args) == 1:
        try:
            timer = float(context.args[0])
            if timer < 0:
                context.bot.send_message(chat_id=update.effective_chat.id, text=f"Negative timer make no sense.")
                return
        except:
            context.bot.send_message(chat_id=update.effective_chat.id, text=f"Usage: /disable [Seconds]")
            return
    elif len(context.args) > 1:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Usage: /disable [Seconds]")
        return
    patterns[str(update.effective_chat.id)]["enabled"]=True
    if timer:
        # Re_disable job init
        if timer > 3600:
            reply = f"The bot is temporarily enabled for {round(timer/3600, 2)} hours."
        elif timer > 60:
            reply = f"The bot is temporarily enabled for {round(timer/60, 2)} minutes."
        else:
            reply = f"The bot is temporarily enabled for {timer} seconds."
        reply+= f"\nAnd will be re-disabled at {datetime.datetime.fromtimestamp(int(time.time()+timer))}."
        if 'job' in context.chat_data:
            old_job = context.chat_data['job']
            old_job.schedule_removal()
        new_job = context.job_queue.run_once(re_enable, timer, context={"chat_id": update.effective_chat.id, "target": False})
    else:
        reply = "The bot is disabled in this chat."
    update_pattern(str(update.effective_chat.id))
    context.bot.send_message(chat_id=update.effective_chat.id, text=reply)

enable_handler = CommandHandler('enable', enable, pass_args=True)
dispatcher.add_handler(enable_handler)
def re_enable(context):
    job = context.job
    target = job.context["target"]
    chat_id = str(job.context["chat_id"])
    patterns[chat_id]["enabled"]=target
    update_pattern(chat_id)
    context.bot.send_message(chat_id=chat_id, text=f"The bot is re-{'enabled' if target else 'disabled'} now.")

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)
dispatcher.add_error_handler(error)

updater.start_polling()

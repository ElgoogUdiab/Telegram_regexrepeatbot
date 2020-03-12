from telegram.ext import Updater
import json
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import requests
import regex as re
from xeger import Xeger
import datetime
import time
from copy import copy
from shutil import copyfile

# random string generator
xeger = Xeger(limit=16)

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
    # backup
    copyfile("pattern.json", "pattern.json.backup")
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
    update_pattern(str(update.effective_chat.id), None)
start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

PATTERN, RESPONSE_TYPE, RESPONSE_PATTERN = range(3)
RESPONSE_TYPE_COUNT = 4
RESPONSE_CUSTOM, RESPONSE_REGEX, RESPONSE_REPEAT, RESPONSE_REPLACE = range(RESPONSE_TYPE_COUNT)
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
    data["message"] = context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"OK! Setting rule {name}.\nNow give me the pattern.\
            \nRemember to add ^ and $ when necessary.\
            \nNote: You can cancel at any time by typing /cancel"
    )
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
        [InlineKeyboardButton("Regex pattern", callback_data=str(RESPONSE_REGEX)),
         InlineKeyboardButton("Custom reply", callback_data=str(RESPONSE_CUSTOM))],
        [InlineKeyboardButton("Just repeat", callback_data=str(RESPONSE_REPEAT)),
         InlineKeyboardButton("Do some replace", callback_data=str(RESPONSE_REPLACE))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.delete_message(
        chat_id = data["message"].chat.id,
        message_id = data["message"].message_id
    )
    data["message"] = context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"OK! The pattern is {pattern}.\nPlease choose the response below",
        reply_markup=reply_markup
    )
    return RESPONSE_TYPE
def define_response_type(update, context):
    response_type = update.callback_query.data
    data = context.user_data
    data.update({"type": response_type})
    table = {
        str(RESPONSE_REGEX):(
            "OK! The reply text a random string that match the given pattern.\nNow give the response pattern.",
            RESPONSE_PATTERN
        ),
        str(RESPONSE_CUSTOM):(
            "OK! The reply text is a piece of custom text.\nNow give the response.",
            RESPONSE_PATTERN
        ),
        str(RESPONSE_REPLACE):(
            "OK! The reply text is the trigger text with some replacement.\nNow give the response.",
            RESPONSE_PATTERN
        ),
        str(RESPONSE_REPEAT):(
            "OK! Just repeat the text.\nThis rule should be functioning now.",
            ConversationHandler.END,
            "Repeat"
        ),
    }
    context.bot.delete_message(
        chat_id = data["message"].chat.id,
        message_id = data["message"].message_id
    )
    if table[response_type][1] != ConversationHandler.END:
        data["message"] = context.bot.send_message(chat_id=update.effective_chat.id, text=table[response_type][0])
        return table[response_type][1]
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text=table[response_type][0])
        data.pop("message")
        data["response"] = table[response_type][2]
        update_pattern(update.effective_chat.id, copy(data))
        data.clear()
        return ConversationHandler.END
        

def define_response(update, context):
    data = context.user_data
    response = update.message.text
    # Error check with early exit
    if data["type"] == str(RESPONSE_REGEX):
        try:
            xeger.xeger(response)
        except:
            context.bot.send_message(chat_id=update.effective_chat.id, text=f"Unable to generate string from the given regex!\nPlease try another regex.")
            return RESPONSE_PATTERN
    elif data["type"] == str(RESPONSE_REPLACE):
        try:
            re.sub(data["pattern"], response, "")
        except:
            context.bot.send_message(chat_id=update.effective_chat.id, text=f"Unable to do the replacement with given pattern!\nPlease try another regex.")
            return RESPONSE_PATTERN
    # Save the setting
    data.update({"response": response})
    context.bot.delete_message(
        chat_id = data["message"].chat.id,
        message_id = data["message"].message_id
    )
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! The reply text is {response}.\nThis rule should be functioning now.")
    data.pop("message")
    update_pattern(update.effective_chat.id, copy(data))
    data.clear()
    return ConversationHandler.END

def cancel(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! Canceled")
    data = context.user_data
    context.bot.delete_message(
        chat_id = data["message"].chat.id,
        message_id = data["message"].message_id
    )
    data.clear()
    return ConversationHandler.END

add_pattern_handler = ConversationHandler(
    entry_points=[CommandHandler('add', add_pattern, pass_args=True)],
    states = {
        PATTERN: [MessageHandler(Filters.text, define_pattern)],
        RESPONSE_TYPE: [
            CallbackQueryHandler(define_response_type,
                pattern="^("+"|".join("("+str(i)+")" for i in range(RESPONSE_TYPE_COUNT))+")$"
            ),
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
        # for name, pattern in patterns[str(update.effective_chat.id)]["patterns"].items():
        #     if re.search(pattern["pattern"], message):
        # Rewriting by map/reduce
        match_length = map(
            lambda name_pattern: (
                sum(
                    (span := it.span())[1]-span[0] for it in re.finditer(name_pattern[1]["pattern"], message)
                ),
                name_pattern[0]
            ),
            patterns[str(update.effective_chat.id)]["patterns"].items()
        )
        result = max(match_length, key=lambda x:x[0])
        if result[0] == 0:
            # No match was found.
            return
        name = result[1]
        pattern=patterns[str(update.effective_chat.id)]["patterns"][name]
        logger.info("Message \"%s\" matches rule \"%s\": %s", message, name, str(pattern))
        if pattern["type"] == str(RESPONSE_REPEAT):
            response = message
        elif pattern["type"] == str(RESPONSE_REGEX):
            response = xeger.xeger(pattern["response"])
        elif pattern["type"] == str(RESPONSE_CUSTOM):
            response = pattern["response"]
        elif pattern["type"] == str(RESPONSE_REPLACE):
            response = re.sub(pattern["pattern"], pattern["response"], message)
        context.bot.send_message(chat_id=update.effective_chat.id, text=response)
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

from telegram import Update, ParseMode, ChatAction
from telegram.ext import Updater, CommandHandler, CallbackContext, ConversationHandler,  MessageHandler, Filters
from tinydb import TinyDB, Query, where
from enum import IntEnum, Enum
from time import sleep
import random
import logging
from logging.handlers import RotatingFileHandler
from constants import TOKEN


def get_logger(log_name=''):
    log_format = '%(asctime)s - %(name)s - %(levelname)-8s - %(message)s'

    log = logging.getLogger(log_name)
    log_formatter = logging.Formatter(log_format)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_formatter)
    log.addHandler(stream_handler)

    file_handler_info = RotatingFileHandler('debug.log', mode='a', maxBytes=20*1024*1024, backupCount=2,
                                            encoding=None, delay=0)
    file_handler_info.setFormatter(log_formatter)
    file_handler_info.setLevel(logging.DEBUG)
    log.addHandler(file_handler_info)

    log.setLevel(logging.DEBUG)

    return log


logger = get_logger(__name__)


class UserStates(IntEnum):
    START = 0
    NAME = 1
    LEVEL = 2
    AGE = 3
    HOBBIES = 4


class DataState(IntEnum):
    NOT_ASKED = 1
    ASKED = 2
    ANSWER_GIVEN = 3


English_levels = [
    ('A1', "Elementary"),
    ('A1+', "..."),
    ('A2', "Pre Intermediate"),
    ('A2+', "..."),
    ('B1', "Intermediate"),
    ('B1+', "..."),
    ('B2', "Upper Intermediate"),
    ('B2+', "..."),
    ('C1', "Advanced"),
    ('C1+', "..."),
    ('C2', "Proficient"),
]

English_levels_str = "\n".join(["{} – {}".format(item[0], item[1]) for item in English_levels])
English_level_names = [item[0] for item in English_levels]

db = TinyDB('db.json')


def link_to_user(user_data):
    uid = user_data['id']
    name = user_data['name']
    nick_name = user_data['nick_name']
    link = '<a href="{}">{}</a>'.format(uid, name)
    if nick_name:
        link = '{} (@{})'.format(name, nick_name)
    return link


def logger_user_data(userid_or_instance, user_nick_name=None):
    if user_nick_name is None:
        uid = userid_or_instance['id']
        nick_name = userid_or_instance['nick_name']
        return "user(id={}, nick_name={})".format(uid, nick_name)
    else:
        return "user(id={}, nick_name={})".format(userid_or_instance, user_nick_name)


def answered_all_questions(user_id) -> bool:
    user_ = db.search(Query().id == user_id)
    if not user_ or user_[0]['hobbies'] is None:
        return False
    return True


def start(update: Update, context: CallbackContext) -> UserStates:
    user = update.effective_user
    logger.info("/start {} was called".format(logger_user_data(user)))

    result = db.search(Query().id == update.effective_chat.id)
    if result:
        logger.info("/start {}: the user is already in the DB, asking if they want to recreate their form".format(logger_user_data(user)))
        user = result[0]
        context.bot.sendMessage(chat_id=update.effective_chat.id, text="{}, ты уже создал свою анкету, но если ты хочешь что-то изменить, то напиши /cancel, а потом перезапусти бота, чтобы зарегистрироваться заново – возможно, ты сменил имя или же свои взгляды 👀😆"
                                .format(user['name']))

        return None

    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    sleep(1.5)
    context.bot.sendMessage(chat_id=update.effective_chat.id, text='Привет! 👋 \n\nЯ – Бот-помощник. '
                                                                   'Меня создали для того, чтобы помочь тебе найти 🇺🇸 англоговорящего собеседника.')
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    sleep(2)
    context.bot.sendMessage(chat_id=update.effective_chat.id, text='Как я могу к тебе обращатся? 🙃')


    db.insert({
        'id': update.effective_user.id,
        'chat_id': update.effective_chat.id,
        'nick_name': update.effective_user.username,
        'name': None,
        'level': None,
        'age': None,
        'hobbies': None,
        'available': False,
    })

    logger.info("/start {}: the user data was inserted in the DB".format(logger_user_data(user)))
    return UserStates.NAME


def name_handler(update: Update, context: CallbackContext) -> UserStates:
    user = db.search(Query().id == update.effective_user.id)[0]

    logger.info("name_handler: {} is about to enter their name".format(logger_user_data(user)))

    name = update.message.text
    logger.info("name_handler: {} entered '{}' as their name".format(logger_user_data(user), name))

    if name.startswith('/'):
        update.message.reply_text('Тебя действительно зовут {}? 😅\n\nДавай еще раз:'.format(name))
        logger.info("name_handler: {} the name '{}' is invalid and the user is asked to enter another one"
                    .format(logger_user_data(user), name))
        return UserStates.NAME

    db.update({'name': name}, Query().id == update.effective_user.id)
    logger.info("name_handler: {} their name '{}' is added into the DB".format(logger_user_data(user), name))

    # TODO: let this be a menu and add suggestions if a user doesn't know their level.
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    sleep(1.5)
    context.bot.sendMessage(chat_id=update.effective_chat.id, text='Очень приятно 🤝\n\n{}, скажи, какой у тебя уровень '
                                                                   '🇺🇸?'.format(name))

    logger.info("name_handler: {} is asked to enter their English level"
                .format(logger_user_data(user)))
    return UserStates.LEVEL


def level_handler(update: Update, context: CallbackContext) -> UserStates:
    user = db.search(Query().id == update.effective_user.id)[0]
    level_ = update.message.text.upper().replace('А', 'A').replace('В', 'B').replace('С', 'C')

    if level_ not in English_level_names:
        logger.info(
            "level_handler: {} the entered level '{}' is invalid, so the user is asked to enter it again"
            .format(logger_user_data(user), level_))
        context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        sleep(1.5)
        update.message.reply_text("Я тебя не понимаю 🤷🏻‍♂️... Попробуй выбрать из этих:\n" + English_levels_str)
        return UserStates.LEVEL

    level = English_level_names.index(level_)


    db.update({'level': level}, Query().id == user['id'])
    logger.info("level_handler: {} entered their level to be '{}' and it was replaced to '{}'"
                .format(logger_user_data(user), level_, level))

    name = user['name']
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    sleep(1.5)
    context.bot.sendMessage(chat_id=update.effective_chat.id, text='Отлично ✨ \n\nА теперь, {}, скажи, сколько тебе лет?'
                            .format(name))
    logger.info("level_handler: {} is asked to enter their age".format(logger_user_data(user)))

    return UserStates.AGE


def age_handler(update: Update, context: CallbackContext) -> None:
    user = db.search(Query().id == update.effective_chat.id)[0]
    age = update.message.text

    if not age.isnumeric() or int(age) <= 0 or int(age) > 120:
        logger.info(
            "age_handler: {} entered invalid age ('{}') and was asked to enter it again"
            .format(logger_user_data(user), age)
        )

        context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        sleep(1.5)
        update.message.reply_text(
            "{}, тебе действительно {} лет? Что-то не вериться... \n\nДавай еще раз попробуем 😉"
            .format(user['name'], age))
        return UserStates.AGE

    db.update({'age': int(age)}, Query().id == update.effective_user.id)
    logger.info(
        "age_handler: {} entered their age to be '{}'".format(logger_user_data(user), age))

    name = user['name']
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    sleep(1.5)
    context.bot.sendMessage(chat_id=update.effective_chat.id, text='Вау! Осталось чуть-чуть! 🔥 \n\n'
                                                                   '{}, расскажи, чем ты увлекаешься и что тебе интересно?'
                            .format(name))
    logger.info(
        "level_handler: {} was asked to enter their hobbies".format(logger_user_data(user))
    )

    return UserStates.HOBBIES


def hobbies_handler(update: Update, context: CallbackContext) -> UserStates:
    user = db.search(Query().id == update.effective_user.id)[0]
    hobbies = update.message.text

    if hobbies.startswith("/"):
        logger.info("hobbies_handler: {} entered the {} command instead of their hobbies".format(logger_user_data(user), hobbies))
        context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        sleep(1.5)
        context.bot.sendMessage(chat_id=update.effective_chat.id, text='{}, ты действительно увлекаешься {}? 🤯\n\n'
                                                                       'Мне, например, нравится смотреть на голубей – их шаболоны поведения напоминают мне логическое отображение x → rx(1 — x). 🧐'
                                                                       '\n\nА что нравится делать тебе?'
                                .format(user['name'], hobbies))
        return UserStates.HOBBIES

    db.update({'hobbies': hobbies}, Query().id == update.effective_user.id)

    logger.info(
        "hobbies_handler: {} entered their hobbies to be '{}'".format(logger_user_data(user), hobbies))
    logger.info(
        "hobbies_handler: {} was suggested to run /available command".format(logger_user_data(user)))

    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    sleep(1.5)
    context.bot.sendMessage(chat_id=update.effective_chat.id, text='Готово! Ты составил свою анкету! 🏁\n\n'
                                                                   'Дальше пиши /available, когда есть свободная минутка '
                                                            'и ты готов с кем-то 🗣 поговорить.\n\nКак говорил Альфонс Алле:\n„Не будь болваном. Никогда не откладывай на завтра то, что можешь сделать послезавтра“ 😉')
    return UserStates.HOBBIES + 1


# TODO: ask confirmation via button and print warning
def cancel(update: Update, context: CallbackContext) -> None:
    before_deletion = db.search(Query().id == update.effective_user.id)

    # check if the user wasn't in the DB
    if not before_deletion:
        logger.info("cancel: {} called /cancel not being themself in the DB"
                    .format(logger_user_data(update.effective_user.id, update.effective_user.username)))
        context.bot.sendMessage(chat_id=update.effective_chat.id, text="Ты не можешь использовать эту команду, пока не ответишь на все вопросы 😉")
        return

    user = before_deletion[0]

    logger.info("cancel: {} called /cancel command".format(logger_user_data(user)))
    logger.debug("cancel: {} called /cancel and their data was: {}"
                 .format(logger_user_data(user), str(before_deletion)))

    db.remove(where('id') == update.effective_user.id)
    after_deletion = db.search(Query().id == update.effective_user.id)

    logger.debug("cancel: {} called /cancel and now their data in the DB is: {}"
                 .format(logger_user_data(user), str(after_deletion)))

    context.bot.sendMessage(chat_id=update.effective_chat.id, text='Я удалил все записи о тебе 🗑')


def available(update: Update, context: CallbackContext) -> None:
    # TODO: refactor
    if not answered_all_questions(update.effective_user.id):
        logger.info("available: user(id={}, nick_name={}) didn't answer all questions, but called /available"
                    .format(update.effective_user.id, update.effective_user.username))
        context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        sleep(1)
        context.bot.sendMessage(chat_id=update.effective_chat.id,
                                text='Ты не можешь начать поиск, пока не ответишь на все вопросы 😉')
        return None

    user = db.search(Query().id == update.effective_user.id)[0]

    if user['available']:
        logger.info("available: user(id={}, nick_name={}) is already available, but called again /available"
                    .format(update.effective_user.id, update.effective_user.username))
        context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        sleep(1)
        context.bot.sendMessage(chat_id=update.effective_chat.id,
                                text='Не нужно злоупотреблять командами! 🤨\n\n'
                                     'Общайтесь! Професионалами в любом деле становятся только через кровь, пот и слёзы.\n\n'
                                     'Так что, {}, перебори свой страх стеснения, если Английский для тебя не пустое место 😎'.format(user['name']))
        return None

    available_partners_ = db.search(Query().available == True)
    available_partners = [p for p in available_partners_ if p['id'] != update.effective_user.id]
    logger.info("available: {} called /available".format(logger_user_data(user)))
    logger.debug("available: ALL (including with different level) available partners for {} are: {}"
                 .format(logger_user_data(user), [logger_user_data(p) for p in available_partners]))

    db.update({'available': True}, Query().id == update.effective_user.id)
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    sleep(1)
    context.bot.sendMessage(chat_id=update.effective_chat.id, text='Ты установил свой статус на 🏝 "доступен".'
                                                                   '\n\nЕсли твои планы, к несчастью, поменяются, ты всегда можешь написать /busy, чтобы прекратить поиск 😏')

    partner = None
    if available_partners:
        level = db.search(Query().id == update.effective_user.id)[0]['level']
        level_range = (max(0, level - 3), min(10, level + 3))

        # TODO: exclude visited partners so that they're chosen more "randomly".
        near_same_level_available_partners = []
        for p in available_partners:
            if level_range[0] <= p['level'] <= level_range[1]:
                near_same_level_available_partners.append(p)
        partner = random.choice(near_same_level_available_partners or [None])

        logger.debug("available: available partners for {} are: {}; the chosen one: {}"
                     .format(logger_user_data(user), [logger_user_data(p) for p in near_same_level_available_partners],
                             logger_user_data(partner) if partner is not None else None))

    if not partner:
        logger.info("available: {} called /available and no partner was found for them".format(logger_user_data(user)))
        context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        sleep(1)
        context.bot.sendMessage(chat_id=update.effective_chat.id, text='Когда я найду тебе собеседника, я дам тебе знать'
                                                                   ' – жди сигнала 🔔!')
    else:
        context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        sleep(1.5)
        text = 'Я нашел тебе собеседника! 😎\n\nЕго зовут {}, ему {}, уровень – {}, ' \
               'увлечения:\n{}\n\nБудь смелее и сделай первый шаг!'

        context.bot.sendMessage(chat_id=update.effective_chat.id,
                                text=text.format(link_to_user(partner), partner['age'],
                                                 English_level_names[partner['level']], partner['hobbies']),
                                parse_mode=ParseMode.HTML)

        me = db.search(Query().id == update.effective_user.id)[0]
        context.bot.sendMessage(chat_id=partner['chat_id'],
                                text=text.format(link_to_user(me), me['age'], English_level_names[me['level']], me['hobbies']),
                                parse_mode=ParseMode.HTML)


def list_handler(update: Update, context: CallbackContext) -> None:
    if not answered_all_questions(update.effective_user.id):
        logger.info("list: user(id={}, nick_name={}) didn't answer all questions, but called /list"
                    .format(update.effective_user.id, update.effective_user.username))
        context.bot.sendMessage(chat_id=update.effective_chat.id,
                                text='Ты не можешь использовать эту комманду, пока не ответишь на все вопросы 😉')
        return None

    user = db.search(Query().id == update.effective_user.id)[0]

    logger.info("list_handler: {} called /list".format(logger_user_data(user)))

    text = ""
    for member in db.all():
        link = link_to_user(member)
        text += link + " | {} | {} y.o. \n".format(English_level_names[member['level']], member['age'])

    logger.debug("list_handler: {} called /list and the result is: {}".format(logger_user_data(user),
                                                                              text.replace('\n', '; ')))

    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    sleep(1)
    context.bot.sendMessage(chat_id=update.effective_chat.id, text=text, parse_mode=ParseMode.HTML, disable_web_page_preview = False)


def busy(update: Update, context: CallbackContext) -> None:
    if not answered_all_questions(update.effective_user.id):
        logger.info("busy: user(id={}, nick_name={}) didn't answer all questions, but called /busy"
                    .format(update.effective_user.id, update.effective_user.username))
        context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        sleep(1)
        context.bot.sendMessage(chat_id=update.effective_chat.id,
                                text='Ты не можешь использовать эту комманду, пока не ответишь на все вопросы 😉')
        return None

    user = db.search(Query().id == update.effective_user.id)[0]

    logger.info("busy: {} called /busy".format(logger_user_data(user)))

    db.update({'available': False}, Query().id == update.effective_user.id)

    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    sleep(1)
    context.bot.sendMessage(chat_id=update.effective_chat.id, text='Ты установил свой статус на 🏋️‍♂️ "недоступен".\n\nКак только у тебя снова появится минутка, пиши /available и я подберу тебе собеседника\n\nP.S. «Если сможете совершенствоваться всего на 1% каждый день в течение одного года, к концу этого периода вы станете в 37 раз лучше самого себя», – Джеймс Клир, «Атомные привычки» 😉')


# TODO: restrict user in the group from typing until they register and show them help message
def main():
    updater = Updater(TOKEN)

    updater.dispatcher.add_handler(CommandHandler('available', available))
    updater.dispatcher.add_handler(CommandHandler('busy', busy))
    updater.dispatcher.add_handler(CommandHandler('list', list_handler))
    updater.dispatcher.add_handler(CommandHandler('cancel', cancel))

    updater.dispatcher.add_handler(ConversationHandler(
        entry_points=[CommandHandler('start', start)],

        fallbacks=[CommandHandler('cancel', cancel)],

        states={
            UserStates.START: [MessageHandler(Filters.text, start)],
            UserStates.NAME: [MessageHandler(Filters.text, name_handler)],
            UserStates.LEVEL: [MessageHandler(Filters.text, level_handler)],
            UserStates.AGE: [MessageHandler(Filters.text, age_handler)],
            UserStates.HOBBIES: [MessageHandler(Filters.text, hobbies_handler)]
        }
    ))

    updater.dispatcher.add_handler(CommandHandler('start', start))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()

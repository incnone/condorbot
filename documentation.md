# Condorbot Documentation (for CoNDOR Season 4)

Version: 0.4.5

## Registering

If you haven't already, please register your twitch account and timezone with the bot, by typing in the main channel:

- `.stream eladdifficult`
- `.timezone US/Eastern`

A full list of allowed timezones can be found [here](https://github.com/incnone/condorbot/blob/master/data/tz_list.txt). These are case-sensitive.

You may type `.userinfo` to see your user info at any time, or `.userinfo Elad` to see the user info of a different user on the server (note: this refers to users by their Discord name).

## Alerting staff

If anything goes wrong with the bot at any time (and the bot is still online), you can send an automated alert to CoNDOR Staff by typing `.staff`. The bot will respond that staff has been alerted. If the bot does not respond, you should contact CoNDOR Staff directly (the bot is probably broken).

## Scheduling your match

When a new week begins, you should see two channels appear on the sidebar, one for each of your races. These will be named after the racers in the match (e.g. `#eladdifficult-incnone`). This channel is private to you, your opponent, and CoNDOR Staff. You should use it to schedule your match for the week. Discuss possible times with your opponent. 

When you have settled on a time, one of you should suggest the time formally by typing, e.g., `.suggest February 14 3:30p`. This time is given in your own local time. The bot accepts 24-hour time formats: `.suggest February 14 15:30`.

The bot will respond with messages outputting this time in each racer's local time; both racers should then confirm the time with `.confirm`. (If the time is wrong, you may `.suggest` a new time.) This schedules the match. The #schedule channel and the Google Doc will be updated with the match time.

## Before your match

30 minutes before your match, the bot will PM you an alert that the match is about to start. It will also notify you in channel with an @mention in the channel. These notifications may break if the bot is down; you are responsible for arriving at your match on time. Bot notifications will repeat at 15 and 5 minutes before the match.

Sometime within this period, you should go into your match channel and type `.here`. This lets the bot know that you're around for your match.

At the time you've scheduled for your race, a race room will open. The race will not immediately start -- don't worry! Both racers will need to type `.ready` before the race begins.

## During your match

After your race room has opened, a seed for the first race will be shown in the room headbar. After you've entered this seed (but before you've hit enter to begin playing), and once you are ready for the race to begin, type `.ready`. Once both racers have typed `.ready`, the bot will begin a 10-second countdown, after which the race will begin. You may type `.unready` to undo an earlier `.ready`.

After you've completed the game (stepped on the final staircase), type `.done` or `.d` to indicate that you've completed the race. The bot will record as the race winner the first racer to type `.d` or `.done`. If you disagree with results of the race, you may type `.contest` to mark the race as contested and alert CoNDOR Staff.

If you have typed `.done` in error, you should immediately type `.undone`. The race will then continue.

If at any time something goes wrong and you and your opponent both wish to cancel the race, both of you should type `.cancel`. If both racers type `.cancel`, the race will be cancelled and a new race will begin.

After the first race is over, the second race will begin; again both racers will have to type `.ready` for the second race to actually start the race. There will then be a third race (regardless of the outcome of the first two races). After three races have been completed, the match will be automatically recorded.
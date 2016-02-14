# Condorbot Admin Documentation (for CoNDOR Season 4)

Version: 0.2

## Organization

These commands should be entered in the #adminchat channel.

- `.makeweek <week_number>` : Makes the race rooms for the specified race number, e.g., you should call `.makeweek 1` once at the beginning of this week, after the matchups have been put on the Google Doc. If this command breaks during execution (this happens sometimes, I think due to request timeouts on the google sheet), simply call it again (`.makeweek 1`). It should make the rooms correctly (possibly with one duplicate room, if it broke at exactly the wrong time; you should check for this).

- `.closeallracechannels` : Closes all the private race channels. You almost certainly don't want to call this unless something has gone very wrong.

## Races

These commands should be entered in a race channel, during a match.

- `.forcecancel` : Cancels the current race. You will probably need to call `.forcemakenew` after this command to start the next race.

- `.forceforfeit <discord_name>` : Force a racer to forfeit the race.

- `.forcerecordrace [winner | -draw] [time_winner [time_loser]] [-seed seed_number]` : Records a race that the bot did not record (e.g. if it was down). This command is untested atm (warning). Examples:
    - `.forcerecordrace eladdifficult` records eladdifficult as the winner.
    - `.forcerecordrace -draw` records a draw. (This is a bit untested: warning.)
    - `.forcerecordrace eladdifficult 5:08.07 5:12.12 -seed 12345` records eladdifficult as the winner, with a time of 5:08.07, and his opponent as the loser, with a time of 5:12.12, playing on the seed 12345.

- `.forcenewrace` : Force the bot to make a new race. This cancels any race in progress.
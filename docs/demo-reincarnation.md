# Demo script — the reincarnation (90 seconds)

Exact sequence for recording the `v0.2.0` demo. Every line is a real command with real output;
nothing is mocked and nothing is typed off-screen. Record with `asciinema rec rebirth.cast`
(or a screen GIF); keep the terminal at 100×32, dark theme, a monospace with 《》 glyphs.

## Before recording
```bash
export ALL41N14LLA_VAULT=/tmp/demo-vault       # a clean, throwaway vault
mkdir -p /tmp/prey && cd /tmp/prey
printf '# Salon Ops\n\nHow the front desk runs when nobody is at it.\n\n## Rules\n- Never text a client after 9pm.\n- Always confirm the day before.\n' > README.md
printf '"""Booking engine: one function, one calendar."""\n' > app.py
```

## Take (≈90 s)
1. **0:00** `all41n14lla reincarnate` — answer the eight questions out loud, one line each. Pause
   one beat after *"And what do you name it?"* Let the 《Confirmed.》 lines land.
   Last line on screen: *"You wake in a cave. It is dark. Nimbus is online."*
2. **0:35** `all41n14lla devour /tmp/prey` — the table appears; **nothing is written**. Read the
   last line aloud: *"Nothing devoured."*
3. **0:45** `all41n14lla devour /tmp/prey --accept 1,2` — two 《Confirmed.》 lines and the meal
   episode.
4. **0:55** `cat $ALL41N14LLA_VAULT/constraints/*.md` — show `source:` and `source_hash:` in the
   frontmatter. Say: *"where it came from is in the file."*
5. **1:05** `all41n14lla recall "text a client"` — the devoured rule comes back as a constraint.
6. **1:15** `all41n14lla evolve` — *"Tier: Sage — answers what it is asked; every act is yours."*
7. **1:25** `all41n14lla wire --dry-run` — every client it would connect to. Cut.

## The three lines to say, verbatim
- "Your last thoughts become its first memories."
- "It eats only what you point it at, and only after you say yes."
- "Every memory tells you where it came from."

## After
`unset ALL41N14LLA_VAULT`. Delete `/tmp/demo-vault` and `/tmp/prey` by hand.

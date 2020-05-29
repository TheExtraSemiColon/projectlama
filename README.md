# projectlama
Leg Alle Minpunten Af

[L.A.M.A.](https://boardgamegeek.com/boardgame/266083/llama) is a board game we love to play. This repository is our attempt to write an AI and a GUI to play this.

```python
pip install -r requirements_dev.txt
# For Testing and Training of bots
python test-arena.py
# For scannning the Q-Table
python scan.py 
# For Playing the game
python lama-server.py # in one terminal
python lama-client.py # in another and more
```

Logging of the gamestates is done as follows:
Keyword- Meaning, Stored data
1) nG - new Game, Game Number
2) nT - new Test, Date&Time
2) nR - new Round, /none/
3) tC - top Card, top card
4) pT - player Turn; Alias of the player who is active, their hand, and their action(f, d or p)
5) rE - round End, scores of all the players
6) gE - game End, winner
7) tE - End of Testing

from .constants import State, Prompt, GameErrors
from .deck import Deck
from .players import Player, NetworkPlayer
from .utils import prompter, plus_one
from collections import defaultdict, deque
from itertools import cycle
from twisted.web import http, server, xmlrpc
from datetime import datetime
import matplotlib.pyplot as plt
import random
import string
import pickle


class Game:
    def __init__(self):
        self.history = []
        self.state = None
        self.test = False
        self.num_games = 0
        self.tot_games = 0
        self.bot_no = 0
        self.turn_cycler = None
        self.turn = None

    def init(self):
        if self.test:
            self.state = State.TEST_BEGIN
        else:
            self.state = State.GAME_BEGIN

    def advance_turn(self):
        self.turn = next(self.turn_cycler)

    def calc_score(self):
        for player in self.players:
            player.calc_score()
        for player in self.players:
            if player.score >= 40:
                return True
        return False


class NetworkGame(Game):
    def __init__(self, game_id):
        self.game_id = game_id
        self.players = []
        self.error_queue = deque()
        self.input_wait_queue = deque()
        self.global_message_queue = defaultdict(deque)
        self.score_queue = defaultdict(deque)
        super().__init__()

    def init(self):
        super().init()
        if self.test:
            resp = prompter(f"Add a Q-Agent for Training or Testing?(Y/N)", [])
            if resp == "y" or resp == "Y":
                self.add_bot(True)
                resp = prompter(f"Enter 1 to Train AI, and 2 to Test already trained AI", [])
                if resp == "1":
                    self.CUM_REW = 0
                    self.CUM_PEN = 0
                    self.x1 = []
                    self.y1 = []
                    self.y2 = []
                elif resp == "2":
                    self.Won_Games = 0.0
                    for player in self.players:
                        if player.isQbot:
                            player.Play_Init()
                            
            self.tot_games = prompter(f"How many Games?", [])
            self.bot_no = int(prompter(f"How many bots?", []))
            for i in range(self.bot_no):
                self.add_bot()

            if len(self.input_wait_queue):
                self.input_wait_queue.pop()
        else:
            self.input_wait_queue.pop()

        self.turn_cycler = cycle(self.players)
        self.turn = next(self.turn_cycler)

    def add_player(self, alias):
        if len(self.players) < 6:
            player_token = ''.join(
                random.choices(
                    string.ascii_uppercase +
                    string.digits,
                    k=5))
            self.players.append(NetworkPlayer(alias, player_token))
            return {"token": player_token}
        else:
            return {"error": "Game is full"}

    def add_bot(self, Q = False):
        if len(self.players) < 6:
            if not Q:
                alias = "Bot" + str(self.num_bots()+1)
            else:
                alias = "Q-Agent"
            player_token = ''.join(
                random.choices(
                    string.ascii_lowercase +
                    string.digits,
                    k=5))
            new = NetworkPlayer(alias, player_token, Q)
            new.bot(Q)
            self.players.append(new)
            return {"token": player_token}
        else:
            return {"error": "Game is full"}

    def bot_score(self, player):
        score = 0
        uniq_hand = list(set(player.hand))
        increment = sum(map(lambda x: x if x < 7 else 10, uniq_hand))
        score = score + increment
        return score

    def naive_bot(self, player, discard_pile):
        if player.active == False:
            return None
        for card in player.hand:
            if card ==  discard_pile[-1] or card == plus_one(discard_pile[-1]):
                return card
        score = self.bot_score(player)
        if score < 15:
            return "Fold"
        return "Draw"

    def num_bots(self):
        num = 0
        for temp in self.players:
            if temp.isbot:
                num+=1
        return num

    def find_player(self, player_token):
        # validate guarantees you will find one
        for player in self.players:
            if player.token == player_token:
                return player
        return None

    def _broadcast_message(self, message, typ='NORMAL'):
        queue = self.global_message_queue if typ == 'NORMAL' else self.score_queue
        for player in self.players:
            queue[player.token].append(message)

    def evaluate(self, state, info):
        log_info = open("logs.txt", "a")

        Store = True

        for player in self.players:
            if player.isQbot and player.Train:
                Store = False
        
        if state is State.TEST_BEGIN:
            if Store:
                log_info.write(f"nT\n{str(datetime.now())}\n\n")
            return None, State.GAME_BEGIN

        if state is State.GAME_BEGIN:
            if self.test:
                self.num_games+=1
                if Store:
                    log_info.write(f"nG {str(self.num_games)}\n\n")
            else:
                if Store:
                    log_info.write(f"nG {str(datetime.now())}\n\n")

            return None, State.ROUND_BEGIN

        elif state is State.ROUND_BEGIN:
            # deck
            self.deck = Deck()
            self.deck.start()

            #Logging the top card when the round starts
            if Store:    
                log_info.write(f"nR\n\n")
                log_info.write(f"tC\n{str(self.deck.discard_pile[-1])}\n\n") 
            self.package_send2 = {}
            
            # first draw
            for player in self.players:
                player.init()
            for i in range(6):
                for player in self.players:
                    player.draw(self.deck)

            return None, State.ROUND_CONT

        elif state is State.ROUND_CONT:
            if info is not None and info.isdigit():
                info = int(info)

            n = 0
            for temp in self.players:
                if temp.active:
                    n+=1
            if n==0:
               return None, State.ROUND_END

            player = self.turn 
            deck = self.deck
            if player.active:
                if not deck.playable(player.hand):
                    active_players = sum(map(lambda x: x.active, self.players))
                    if not len(deck.main_pile) or active_players is 1:
                        player.deactivate()
                        return None, State.ROUND_END
                    else:
                        if info == "Fold":
                            player.deactivate()
                            self._broadcast_message(f"<span class='l-player-name'>{player.alias}</span> has folded")
                            if Store:
                                log_info.write(f"pT\n{player.alias}\n")
                                for x in player.hand:
                                    log_info.write(f"{str(x)} ")
                                log_info.write(f"\nf\n \n")
                                log_info.write(f"tC\n{str(self.deck.discard_pile[-1])}\n\n")
                            log_info.close()
                            
                        elif info == "Draw":
                            if Store:
                                log_info.write(f"pT\n{player.alias}\n")
                                for x in player.hand:
                                    log_info.write(f"{str(x)} ")
                            player.draw(self.deck)
                            self._broadcast_message(f"<span class='l-player-name'>{player.alias}</span> has drawn")
                            if Store:
                                log_info.write(f"\nd\n\n")
                                log_info.write(f"tC\n{str(self.deck.discard_pile[-1])}\n\n")                           
                            log_info.close()                        
                        else:
                            return Prompt.FD, State.ROUND_CONT
                else:
                    if info is None:
                        return Prompt.PF, State.ROUND_CONT
                    else:
                        if info == "Fold":
                            player.deactivate()
                            self._broadcast_message(f"<span class='l-player-name'>{player.alias}</span> has folded")
                            if Store:
                                log_info.write(f"pT\n{player.alias}\n")
                                for x in player.hand:
                                    log_info.write(f"{str(x)} ")
                                log_info.write(f"\nf")
                                log_info.write(f"tC\n{str(self.deck.discard_pile[-1])}\n\n")
                            log_info.close()
                        elif deck.playable(info) and info in player.hand:
                            if Store:
                                log_info.write(f"pT\n{player.alias}\n")                            
                                for x in player.hand:
                                    log_info.write(f"{str(x)} ")
                            tbd = player.delete(info)
                            deck.discard(tbd)
                            self._broadcast_message(f"<span class='l-player-name'>{player.alias}</span> has played {tbd}")
                            if Store:
                                log_info.write(f"\np{tbd}\n")
                            # round ender if finishes hand
                            if not len(player.hand):
                                if Store:
                                    log_info.write(f"\nhF\n\n")
                                return None, State.ROUND_END
                            else:
                                if Store:
                                    log_info.write(f"\ntC\n{str(self.deck.discard_pile[-1])}\n\n")
                            log_info.close()
                        else:
                            return Prompt.PF, State.ROUND_CONT

            if not self.test:
                self.advance_turn()
            return None, State.ROUND_CONT

        elif state is State.ROUND_END:
            over = self.calc_score()
            scores = [(player.alias, player.score) for player in self.players]
            if Store:
                log_info.write(f"rE\n")
                for player in self.players:
                    log_info.write(f"{player.alias},{player.score}\n")
                log_info.write('\n')
            self._broadcast_message(scores, typ='SPECIAL')
            if over:
                winner = sorted(self.players,
                                key=lambda x: x.score)[0]
                if winner.isQbot and not winner.Train:
                    self.Won_Games+=1
                self._broadcast_message({'winner': winner.alias}, typ='SPECIAL')
                if Store:
                    log_info.write(f"gE\n")
                    log_info.write(f"{winner.alias}\n\n")
                    log_info.close()
                return None, State.GAME_END
            else:
                log_info.close()
                return None, State.ROUND_BEGIN

        elif state is State.GAME_END and self.test:
            if int(self.num_games) < int(self.tot_games):
                print(f"GN {self.num_games}")
                return None, State.GAME_BEGIN
            else:
                for player in self.players:
                    if player.isQbot and not player.Train:
                        Win_Perc = float(self.Won_Games/self.num_games) * 100
                        print(f"Win Percentage of the Q-Agent: {Win_Perc}")
                if Store:
                    log_info.write(f"tE\n")
                log_info.close()
                return None, State.TEST_END

    def get_info(self, prompt):
        if prompt is None:
            return None
        elif prompt is Prompt.FD:
            self.input_wait_queue.append("FD")
            return None
        elif prompt is Prompt.PF:
            self.input_wait_queue.append("PF")
            return None

    def step(self, info):
        if (self.test) and (self.state is not State.TEST_END):
            prompt, new_state = self.evaluate(self.state, str(info))
            #print(f"{self.game_id} stepping from {str(self.state)} to {str(new_state)}")
            self.state = new_state
            return None

        elif (not self.test) and (self.state is not State.GAME_END):
             prompt, new_state = self.evaluate(self.state, str(info))
             print(f"{self.game_id} stepping from {str(self.state)} to {str(new_state)}")
             self.state = new_state
             return self.get_info(prompt)

class TestMaster(NetworkGame):
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        pass

    def __init__(self):
        super().__init__(str(1))
        self.test = True

    def init(self):
        super().init()
        #State moves from TEST_BEGIN to GAME_BEGIN
        self.step(None)

    def run(self):
        while self.state is not State.TEST_END:

            if self.state is State.GAME_BEGIN or self.state is State.ROUND_BEGIN:
                self.step(None)

            if self.state is State.ROUND_CONT:

                num_players = 0
                for temp in self.players:
                    if temp.active:
                        num_players+=1
                if num_players==0:
                    self.state = State.ROUND_END

                
                if not self.turn.isQbot:
                    move = self.naive_bot(self.turn, self.deck.discard_pile)
                else:
                    move = self.turn.Q_Bot_Logic(self.deck, num_players)

                if move is not None:
                    self.step(move)
                self.advance_turn()

            if self.state is State.ROUND_END:
                for player in self.players:
                    if player.isQbot:
                        player.PREV_REWARD = 0
                        player.PREV_STATE = 0
                        player.CURR_STATE = 0
                self.step(None)

            if self.state is State.GAME_END:
                for player in self.players:
                    if player.isQbot and player.Train:
                        self.CUM_REW+=player.G_Rew()
                        self.CUM_PEN+=player.G_Pen()
                        if (self.num_games%200) == 0:
                            player.Decay_EPSILON(self.num_games, self.tot_games)
                        if (self.num_games%200) == 0:
                            self.x1.append(self.num_games)
                            self.y1.append((self.CUM_REW)/200)
                            self.y2.append((self.CUM_PEN)/200)
                            self.CUM_REW = 0
                            self.CUM_PEN = 0
                        player.GAME_REW = 0
                        player.GAME_PEN = 0
                    player.score = 0
                self.step(None)

        print(f"Testing Completed. Check logfile for history.")

        for player in self.players:
            if player.isQbot:
                player.EPSILON = 0.5
                Train = player.Train
                if player.Train:
                    arr = player.Q_TABLE
                    pickle.dump(arr, open("sample.pkl", "ab"))
                    plt.plot(self.x1, self.y1, label = "Rewards")
                    plt.plot(self.x1, self.y2, label = "Penalties")
                    plt.xlabel('Game num')
                    plt.ylabel('Penalties/Rewards')
                    plt.title('Graph')
                    plt.legend()
                    plt.show()
                break


class GameMaster(xmlrpc.XMLRPC):
    def __init__(self):
        self.games = {}
        xmlrpc.XMLRPC.__init__(self)

    @staticmethod
    def __apply_CORS_headers(request):
        request.setHeader('Access-Control-Allow-Origin', '*')
        request.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        request.setHeader('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Access-Control-Allow-Origin')

    def render_OPTIONS(self, request):
        GameMaster.__apply_CORS_headers(request)
        request.setResponseCode(http.OK)
        request.write('OK'.encode('utf-8'))
        request.finish()
        return server.NOT_DONE_YET

    @xmlrpc.withRequest
    def xmlrpc_open(self, request):
        GameMaster.__apply_CORS_headers(request)
        game_id = ''.join(
            random.choices(
                string.ascii_uppercase +
                string.digits,
                k=5))
        g = NetworkGame(game_id)
        g.input_wait_queue.append("start")
        self.games[game_id] = g
        return game_id

    @xmlrpc.withRequest
    def xmlrpc_validate(self, request, game_id, player_token=None):
        GameMaster.__apply_CORS_headers(request)
        if game_id not in self.games:
            return False
        elif player_token is not None:
            search = sum(map(lambda x:x.token == player_token, self.games[game_id].players))
            if not search:
                return False
        return True

    @xmlrpc.withRequest
    def xmlrpc_join(self, request, game_id, alias):
        GameMaster.__apply_CORS_headers(request)
        return self.games[game_id].add_player(alias)

    @xmlrpc.withRequest
    def xmlrpc_add(self, request, game_id):
        GameMaster.__apply_CORS_headers(request)
        try:
            _ = pickle.load(open("sample.pkl", "rb"))
            return self.games[game_id].add_bot(True)
        except (OSError, IOError) as e:
            return self.games[game_id].add_bot()

    @xmlrpc.withRequest
    def xmlrpc_query_state(self, request, game_id, player_token):
        GameMaster.__apply_CORS_headers(request)
        result = {}
        result["message"] = []
        result["score"] = []

        if not self.xmlrpc_validate(request, game_id, player_token=player_token):
            result["error"] = "Invalid token, game pair presented"
            return result

        game = self.games[game_id]
        player = game.find_player(player_token)
        curr_state = game.state


        if not len(game.input_wait_queue):
            _ = game.step(None)

        # Game not begun, lobby state to be sent
        if curr_state is None:
            result["game_state"] = "none"
            result["action"] = "wait"
            result["players"] = list(map(lambda x: x.alias, game.players))

        if curr_state is State.ROUND_CONT:

           
            result["game_state"] = "round_running"
            result["whose_turn"] = game.turn.alias
            result["hand"] = player.hand
            result["top_card"], result["top_card_v"] = game.deck.top_card()

                
            if game.turn == player:
                result["my_turn"] = "yes"
                if len(game.input_wait_queue):
                    result["expected_action"] = game.input_wait_queue.pop()
                    

        if len(game.error_queue):
            result["error"] = game.error_queue.pop() 

        msg_for_player = game.global_message_queue[player.token]
        while len(msg_for_player):
            result["message"].append(msg_for_player.pop())

        special_msg_for_player = game.score_queue[player.token]
        while len(special_msg_for_player):
            result["score"].append(special_msg_for_player.pop())

        if game.turn is not None:
            if game.turn.isbot:
                    _ = game.step(game.naive_bot(game.turn, game.deck.discard_pile))
        
        return result

    @xmlrpc.withRequest
    def xmlrpc_push_input(self, request, game_id, player_token, inp):
        GameMaster.__apply_CORS_headers(request)
        result = {}

        if not self.xmlrpc_validate(request, game_id, player_token=player_token):
            result["error"] = "Invalid token, game pair presented"
            return result

        game = self.games[game_id]
        player = game.find_player(player_token)
        curr_state = game.state

        if game.turn == player and game.turn.token[0].isupper():
            _ = game.step(inp)
        return True

    @xmlrpc.withRequest
    def xmlrpc_start_game(self, request, game_id, player_token):
        GameMaster.__apply_CORS_headers(request)
        result = {}

        if not self.xmlrpc_validate(request, game_id, player_token=player_token):
            result["error"] = "Invalid token, game pair presented"
            return result

        game = self.games[game_id]
        game.init()

        return result

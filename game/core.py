from .constants import State, Prompt, GameErrors
from .deck import Deck
from .players import Player, NetworkPlayer
from .utils import prompter
from collections import defaultdict, deque
from itertools import cycle
from twisted.web import http, server, xmlrpc
import random
import string


class Game:
    def __init__(self):
        self.history = []
        self.state = None

        self.turn_cycler = None
        self.turn = None

    def init(self):
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
        super().__init__()

    def init(self):
        super().init()
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

    def find_player(self, player_token):
        # validate guarantees you will find one
        for player in self.players:
            if player.token == player_token:
                return player
        return None

    def evaluate(self, state, info):
        if state is State.GAME_BEGIN:
            return None, State.ROUND_BEGIN

        elif state is State.ROUND_BEGIN:
            # deck
            self.deck = Deck()
            self.deck.start()
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

            if not sum(map(lambda x: x.active, self.players)):
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
                        elif info == "Draw":
                            player.draw(self.deck)
                        else:
                            return Prompt.FD, State.ROUND_CONT
                else:
                    if info is None:
                        return Prompt.PF, State.ROUND_CONT
                    else:
                        if info == "Fold":
                            player.deactivate()
                        elif deck.playable(info) and info in player.hand:
                            deck.discard(player.delete(info))

                            # round ender if finishes hand
                            if not len(player.hand):
                                return None, State.ROUND_END
                        else:
                            return Prompt.PF, State.ROUND_CONT

            self.advance_turn()
            return None, State.ROUND_CONT

        elif state is State.ROUND_END:
            over = self.calc_score()
            print_str = ""
            for player in self.players:
                print_str = f"{print_str}Player{player.alias} has score {player.score}...\n"
            if over:
                winner = sorted(self.players,
                                key=lambda x: x.score)[0]
                print_str = f"{print_str}Player{winner.alias} wins.\n"
                for player in self.players:
                    self.global_message_queue[player.token].append(print_str)
                return None, State.GAME_END
            else:
                for player in self.players:
                    self.global_message_queue[player.token].append(print_str)
                return None, State.ROUND_BEGIN

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
        if self.state is not State.GAME_END:
            prompt, new_state = self.evaluate(self.state, info)
            print(f"{self.game_id} stepping from {str(self.state)} to {str(new_state)}")
            self.state = new_state
            return self.get_info(prompt)

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
    def xmlrpc_query_state(self, request, game_id, player_token):
        GameMaster.__apply_CORS_headers(request)
        result = {}

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
            result["top_card"] = top_card = game.deck.top_card()
            if game.turn == player:
                result["my_turn"] = "yes"
                if len(game.input_wait_queue):
                    result["expected_action"] = game.input_wait_queue.pop()

        if len(game.error_queue):
            result["error"] = game.error_queue.pop() 

        msg_for_player = game.global_message_queue[player.token]
        if len(msg_for_player):
            result["message"] = msg_for_player.pop()

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

        if game.turn == player:
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


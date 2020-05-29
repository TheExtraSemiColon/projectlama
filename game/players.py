from .utils import plus_one
from collections import defaultdict
import pickle
import math
import copy
import random

class Player:
    def __init__(self, Q = False, auto=False):
        self.auto = auto
        self.hand = []
        self.active = True
        self.isbot = False
        self.isQbot = Q
        self.score = 0
        if self.isQbot:
            #New parameters added from here
            self.GAME_REW = 0
            self.GAME_PEN = 0
            self.Train = True

            #Q_Table is loaded in or created accordingly
            try:
                self.Q_TABLE = pickle.load(open("sample.pkl", "rb"))
            except (OSError, IOError) as e:
                self.Q_TABLE = defaultdict(int)

            self.ALPHA = 0.4
            self.DISCOUNT_FACTOR = 0.9
            self.EPSILON = 0.5
            #The state can never be 0, so it's okay to initialise as such
            self.PREV_STATE = 0
            self.CURR_STATE = 0

            self.PREV_REWARD = 0
            self.COMPL_REWARD = 10.0
            #self.PLAY_REWARD defined later
            self.DRAW_PENALTY = (-0.5)
            #self.FOLD_PENALTY defined later

    def init(self):
        self.hand = []
        self.activate()

    def deactivate(self):
        self.active = False

    def activate(self):
        self.active = True

    def bot(self, Q):
        self.isbot = True
        self.isQbot = Q

    def draw(self, deck):
        self.hand.append(deck.main_pile.pop())

    def calc_score(self):
        if not len(self.hand):
            if not self.score:
                self.score = 0
            # TODO: Ideally the following should be a choice
            elif self.score < 10:
                self.score = self.score - 1
            else:
                self.score = self.score - 10
        else:
            uniq_hand = list(set(self.hand))
            increment = sum(map(lambda x: x if x < 7 else 10, uniq_hand))
            self.score = self.score + increment
        return self.score

    def delete(self, n):
        i = 0
        while i < len(self.hand):
            if self.hand[i] == n:
                return self.hand.pop(i)
            i = i + 1

    def Play_Init(self):
        self.Train = False

    def G_Rew(self):
        return self.GAME_REW

    def G_Pen(self):
        return self.GAME_PEN

    #This function decays the value of Epsilon exponentially
    #The value of Epsilon is reset in core.py after testing is done
    def Decay_EPSILON(self, game_num, tot_games):
        try: self.c
        except AttributeError: self.c = math.log(50)/float(tot_games)

        self.EPSILON = (0.5) * math.exp(-1 * self.c * float(game_num))

    def encode(self, deck, num_players):
        #Encodes the hand of the player
        #Units is tc; the rest are number of cards for 1,2,..
        #The First Digit from the left shows the number of active players
        index = 0
        tc = deck.discard_pile[-1]
        index = index + tc
        (temp1, temp2) = (False, False)
        num_actions = 2
        for x in self.hand:
            if x == tc:
                temp1 = True
            if x == plus_one(tc):
                temp2 = True
            index = index + int(pow(10, x))
        index = index + num_players*int(pow(10, 8))
        if temp1 and temp2:
            num_actions = 3
        return (index, num_actions)

    def decode(self, index):
        #Returns a list with first element as tc and the rest as the player's hand
        result = []
        result.append(index%10)
        index = int(index/10)
        for i in range(1, 8, 1):
            while index%10 != 0:
                result.append(i)
                index = index - 1
            index = index/10
        return result 

    def Play_Reward(self, card):
        rep = 0
        for temp in self.hand:
            if temp == card:
                rep+=1
        PLAY_REWARD = (card - (rep/2)) * (0.1)
        return PLAY_REWARD

    def Fold_Penalty(self):
        temp_score = self.bot_score(self.hand)
        if temp_score > 13:
            FOLD_PENALTY = -5
        else:
            FOLD_PENALTY = (-1*temp_score)/10
        return FOLD_PENALTY

    def playable(self, deck):
        for card in self.hand:
            if card ==  deck.discard_pile[-1] or card == plus_one(deck.discard_pile[-1]):
                return True

        return False

    def bot_score(self, hand):
        score = 0
        uniq_hand = list(set(hand))
        increment = sum(map(lambda x: x if x < 7 else 10, uniq_hand))
        score = score + increment
        return score

    def Q_Search(self, index, num_actions):
        if self.Q_TABLE[index, 0] == 0:
            for i in range(num_actions):
                self.Q_TABLE[index, i] = random.random()
        return True

    #Decision making and updating the Q-Table happends here
    def Q_Bot_Logic(self, deck, num_players):
        if self.active == False:
            return None
        else:
            index, num_actions = self.encode(deck, num_players)
            _ = self.Q_Search(index, num_actions)

            if self.PREV_STATE == 0:
                self.PREV_STATE = index
            self.CURR_STATE = index     

            exp = random.random()
            temp = []
            for i in range(num_actions):
                temp.append(self.Q_TABLE[index, i])
            MAX_Q_VALUE = max(temp)
            if exp < self.EPSILON and self.Train:
                move = random.randint(0, num_actions-1)
            else:
                move = temp.index(max(temp))

            Reward = 0
            Penalty = 0

            #Deciding on what action to take
            if not self.playable(deck):
                if move == 0:
                    result = "Draw"
                    Penalty = self.DRAW_PENALTY
                else:
                    result = "Fold"
                    Penalty = self.Fold_Penalty()
            elif num_actions == 2:
                if move == 0:
                    for card in self.hand:
                        if card == deck.discard_pile[-1] or card == plus_one(deck.discard_pile[-1]):
                            result = card
                            Reward = self.Play_Reward(card)
                            break
                else:
                    result = "Fold"
                    Penalty = self.Fold_Penalty()
            else:
                if move == 0:
                    result = deck.discard_pile[-1]
                    Reward = self.Play_Reward(result)
                elif move == 1:
                    result = plus_one(deck.discard_pile[-1])
                    Reward = self.Play_Reward(result)
                else:
                    result = "Fold"
                    Penalty = self.Fold_Penalty()

            #Update the Q-Table if the bot is being trained

            #Update the Previous State using the MAX_Q_VALUE with the Discount Factor Formula
            if self.PREV_STATE != self.CURR_STATE and self.Train:
                self.Q_TABLE[self.PREV_STATE, self.PREV_ACT] = (1-self.ALPHA)*(self.Q_TABLE[self.PREV_STATE, self.PREV_ACT]) + (self.ALPHA)*((self.PREV_REWARD) + self.DISCOUNT_FACTOR*(MAX_Q_VALUE))
            
            #Finishing Hand and Folding render the AI inactive, so we update the current Q_VALUE with Discount Factor as 0
            if type(result) is int and len(self.hand)==1:
                Reward+=self.COMPL_REWARD
                if self.Train:
                    self.Q_TABLE[self.CURR_STATE, move] = (1-self.ALPHA)*(self.Q_TABLE[self.CURR_STATE, move]) + (self.ALPHA)*(Reward)

            if result == "Fold" and self.Train:
                self.Q_TABLE[self.CURR_STATE, move] = (1-self.ALPHA)*(self.Q_TABLE[self.CURR_STATE, move]) + (self.ALPHA)*(Penalty)

            self.PREV_STATE = self.CURR_STATE
            self.PREV_ACT = move
            self.PREV_REWARD = (Reward + Penalty)
            self.GAME_PEN+=Penalty
            self.GAME_REW+=Reward

            return result

class NetworkPlayer(Player):
    def __init__(self, alias, token, Q = False):
        self.alias = alias
        self.token = token
        super().__init__(Q)

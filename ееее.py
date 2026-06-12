import random

cards_list = ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]
cards = {"6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10, "A": 11}

card1bot = random.choice(cards_list)
card2bot = random.choice(cards_list)
card1user = random.choice(cards_list)
card2user = random.choice(cards_list)

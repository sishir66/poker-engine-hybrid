import random

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

alpha_list = []

base_word = "_ _ _ _ _"

base_word_list = []


for letter in ALPHABET:
    alpha_list.append(letter)

for letter in base_word:
    if letter == "_":
        base_word_list.append(letter)

base_word_list_copy = base_word_list

def replace_char(word, index, new_char):
    """
    Replace the character at `index` in `word` with `new_char`.
    Returns a new string (since strings are immutable).
    """
    if index < 0 or index >= len(word):
        raise IndexError("Index out of range")
    return word[:index] + new_char + word[index+1:]

def word_loader():

    ref_line = random.randint(1,521)

    refer_word = ""

    with open("wordle_words.txt","r") as name_of_file:
        refer_word = name_of_file.readlines()[ref_line-1]
    return refer_word

target = word_loader()

target_word_list = []

for letter in target:
    target_word_list.append(letter)

target_word_list_copy = target_word_list

def does_it_match(string):
    if string.lower() == target.lower():
        return True
    else:
        False

def configure_what_happened(guess, required_word):
    reference_list_of_target = list(required_word)
    list_of_guess = list(guess)
    list_of_green_indexes = []
    # Make a for loop for all that is GREEN

    for index in range(5):
        if list_of_guess[index] == reference_list_of_target[index]:
            list_of_green_indexes.append(index)
            base_word_list[index] = list_of_guess[index].upper()
            reference_list_of_target[index] = None
            list_of_guess[index] = None
    
    # Now lets make a loop for YELLOW

    for index in range(5):
        if list_of_guess[index]:
            if list_of_guess[index] in reference_list_of_target:
                base_word_list[index] = list_of_guess[index].lower()
                first_occurance_index = reference_list_of_target.index(list_of_guess[index])
                reference_list_of_target[first_occurance_index] = None

    # for letter in guess:
    #     if letter in reference_list_of_target:
    #         if guess.index(letter) == reference_list_of_target.index(letter):
    #             # Same Place Same Letter
    #             variable_for_index = guess.index(letter)
    #             base_word_list[variable_for_index] = letter.upper()
    #             list_of_green_indexes.append(variable_for_index)
    #             reference_list_of_target[variable_for_index] = None

    # Make a loop for all that is YELLOW
    # Loop through indices and don't do the ones that the first one has green for
    # for index in range(5):
    #     if index not in list_of_green_indexes:
    #         # These are the letters that are NOT green
    #         # First check if the letter is in the word
    #         if guess[index] in reference_list_of_target:
    #             base_word_list[index] = guess[index].lower()
    #             reference_list_of_target[index] = None

    
    
    # for letter in guess:
    #     if letter in target:
    #         if guess.index(letter) == target.index(letter):
    #             # This is the GREEN OUTCOME
    #             # create a variable that determines the placement from 0-4 of the letter
    #             variable_for_index = guess.index(letter)
    #             base_word_list[variable_for_index] = letter.upper()
    #             # replace_char(required_word, variable_for_index, "_")
    #             # replace_char(guess, variable_for_index, "_")
    #         else:
    #             # This is the YELLOW outcome
    #             # change the same thing but make it lowercase
    #             variable_for_index = guess.index(letter)
    #             variable_of_target = required_word.index(letter)
    #             base_word_list[variable_for_index] = letter.lower()
    #             # replace_char(required_word, variable_of_target, "_")
    #             # replace_char(guess, variable_for_index, "_")
    #     else:
    #         # This is the GRAY outcome
    #         for alphabetical_thing in alpha_list:
    #             if letter.lower() == alphabetical_thing.lower():
    #                 number = alpha_list.index(alphabetical_thing)
    #                 alpha_list[number] = "0"

print("We are playing a wordle type game. The word you will guess has 5 letters." \
"After your first guess you will be given _ _ _ _ _ which will show the progress you" \
"have made. If there is blank then your guess is incorrect. If its the letter then your " \
"guess is correct and if it's a lowercase letter then the target word has the letter however" \
"it doesn't have the letter in the right spot\n\n")

print("Lets begin\n\n")

current_alpha_phrase = "current alphabet"

while True:
    base_word_list = ["_","_","_","_","_"]
    #for testing purposes
    print("\n\nthe target word is", target )
    user_guess = input("Put in the word: ")
    if user_guess == target.strip():
        print("HOORAYYY YOU GOT ITT! The word was\n\n",target)
        break
    else:
        configure_what_happened(user_guess, target.strip())
        print(base_word_list)
        user_retry = input("Again? y/n: ")
        if user_retry.lower() == "n":
            break
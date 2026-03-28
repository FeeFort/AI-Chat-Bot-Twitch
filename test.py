from safety import should_block_user_input, get_block_message

while True:
    user_text = input()
    user_check = should_block_user_input(user_text)
    if user_check.blocked:
        print("INPUT BLOCKED:", user_check.reasons, "|", user_text)
        print(get_block_message(user_check, stage="input"))

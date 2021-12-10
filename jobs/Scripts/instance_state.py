class ClientInstanceState:
    # client stores state of the both client and server
    def __init__(self):
        self.prev_action_done = True
        self.non_workable_client = False
        self.non_workable_server = False
        self.is_aborted_client = False
        self.is_aborted_server = False

        self.commands_to_skip = 0

    def format_current_state(self):
        return f"""
            Previous actions done: {self.prev_action_done}
            Client has non workable state: {self.non_workable_client}
            Server has non workable state: {self.non_workable_server}
            Is case aborted by client: {self.is_aborted_client}
            Is case aborted by server: {self.is_aborted_server}
        """


class SecondClientInstanceState:
    def __init__(self):
        self.finish_command_received = False

    def format_current_state(self):
        return f"""
            Finish command received: {self.finish_command_received}
        """


class ServerInstanceState:
    # server stores only its state
    def __init__(self):
        self.wait_next_command = True
        self.is_aborted = False
        self.executing_test_actions = False
        self.non_workable_state = False

    def format_current_state(self):
        return f"""
            Wait next command: {self.wait_next_command}
            Is aborted: {self.is_aborted}
            Executing test actions: {self.executing_test_actions}
            Has non workable state: {self.non_workable_state}
        """


class AndroidInstanceState:
    # server stores only its state
    def __init__(self):
        self.executing_test_actions = False
        self.non_workable_state = False

    def format_current_state(self):
        return f"""
            Executing test actions: {self.executing_test_actions}
            Has non workable state: {self.non_workable_state}
        """

# --8<-- [start: saving_state]
import railtracks as rt

# set the configuration globally
rt.set_config(save_state=True)

# or by session 
@rt.session(save_state=False)
async def main(): ...

with rt.Session(save_state=True): ...
# --8<-- [end: saving_state]
import railtracks as rt # ignore this duplicate import, needed for docstring example

@rt.function_node
async def flow_entry():
    pass
# --8<-- [start: saving_state]
import railtracks as rt

# set the configuration globally
rt.set_config(save_state=True)

# or by flow
flow = rt.Flow("my_flow", 
               entry_point=flow_entry,
               save_state=True)
# --8<-- [end: saving_state]
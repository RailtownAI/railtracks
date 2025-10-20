# Image Input

Inputting the images to your agents is quite simple and follows the same logic as text with a few minor differences. There are currently three ways to supply an agent with an image:

1. Path to a local image file
2. Path to a public image online
3. Byte64 encoded data of an image.


Below you can find all three methods in play. Simply provide the **`attachment`** variable to your **`UserMessage`**.

!!! tip "`attachment` accetable values"
    The **`attachment`** can be a **`str`** or a **`list[str]`**

=== "Public URL"

    ```python
    --8<-- "docs/scripts/multimodal.py:public_url"
    ```

=== "Local File"

    ```python
    --8<-- "docs/scripts/multimodal.py:local_file"
    ```

=== "Encoding"

    ```python
    --8<-- "docs/scripts/multimodal.py:data_uri"
    ```

=== "Combined"

    ```python
    --8<-- "docs/scripts/multimodal.py:combined"
    ```

The rest of the invocation (tool_calling, structured_output, etc) will remain the same.
!!! warning "File Types"
    Supported file types will correspond to the file types supported by the underlying LLM used.

!!! warning "Local Chat UI"
    Currently there's no "upload" functionality on the [local chat interaface](../../human_in_the_loop/local_chat_ui.md). This feature will be added in the upcoming weeks.

# Image Output
We're currently not natively supporting outputing images. You can however wrap any image generation logic within a tool and provide your agent with that tool's specifications to achieve this behaviour.
import pymupdf


class MediaParser:
    
def get_pymupdf_text(filepath):
    try:
        pymupdf_text = ""
        doc = pymupdf.open(filepath)
        for i, page in enumerate(doc):
            pymupdf_text += page.get_text() + f"\nPage {i + 1}\n" # get plain text encoded as UTF-8
    except Exception as e:
        return ""
    return pymupdf_text

def clean_text(text):
    """
    Removes NULL bytes and control characters from the provided text 
    to ensure it is XML compatible.
    """
    # Replace NULL bytes and control characters (except for common whitespaces)
    return ''.join(char for char in text if char.isprintable() or char in '\t\n\r')
"""JSON-lines service isolates cp313 tokenizer extensions from Decky host Python."""
import json
import sys
from japanese_reader import JapaneseReader


def main():
    reader = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if reader is None:
                reader = JapaneseReader()
            if request["action"] == "analyze":
                result = reader.analyze(request["regions"])
            elif request["action"] == "lookup":
                result = reader.lookup(request["surface"], request["lemma"], request["reading"])
            else:
                raise ValueError("Unknown reading action")
            response = {"result": result}
        except ImportError:
            response = {"error": "Japanese dependencies are missing. Install the updated dependency archive (fugashi, unidic-lite, jamdict and jamdict-data)."}
        except Exception as error:
            response = {"error": str(error)}
        print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

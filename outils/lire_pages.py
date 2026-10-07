"""Dump the Shamela pages a list of (book, page) names, as JSON.

Notes
-----
The report cites the two printed editions by page, and every such citation
asserts a reading. Checking them one call at a time is impractical, so the
pages are read in one pass through the same Lucene index the server uses.
"""
import json
import sys

from shamela_search.lucene_bridge import LuceneIndex

idx = LuceneIndex()
sortie = {}
for ligne in json.load(open(sys.argv[1])):
    livre, page = ligne
    r = idx.read_passage(int(livre), int(page))
    sortie[f"{livre}-{page}"] = (r.body + "\n" + r.foot) if r else None
json.dump(sortie, open(sys.argv[2], "w"), ensure_ascii=False)
print("lues", sum(1 for v in sortie.values() if v), "sur", len(sortie))

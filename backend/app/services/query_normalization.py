"""Deterministic retrieval cleanup only: no query generation or inferred diagnosis."""
import re

# Conversational filler; retain symptoms, actions, technical identifiers, and negation.
FILLER = set("a an the is are was were what which how should would could can i we you my our please on of for to be been being do does did performed".split())


def retrieval_query(request):
    tokens = re.findall(r"[\w]+(?:[-./][\w]+)*", request.query)
    # ABB is common to this entire ABB-only corpus. An explicit SQL model filter
    # already carries the model identity; avoid repeating it in the semantic query.
    redundant = {"abb"}
    if request.equipment_model:
        redundant.add(request.equipment_model.casefold())
    # Singular/plural family words are already enforced by the SQL family filter.
    family_words = {word.casefold().removesuffix("s") for word in re.findall(r"\w+", request.equipment_family or "")}
    kept = [token for token in tokens if token.casefold() not in FILLER | redundant
            and token.casefold().removesuffix("s") not in family_words]
    return " ".join(kept) if kept else request.query

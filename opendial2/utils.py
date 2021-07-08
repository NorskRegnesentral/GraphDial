import re
from typing import Set

NODE_REGEX = "\\((\\w+?)\\:(\\w+?)( .+?)?\\)"

def normalise_query(cypher_query:str):
    cypher_query = cypher_query.replace("\n", " ")
    cypher_query = re.sub("\\s+\\)", ")", cypher_query)
    cypher_query =  re.sub("\\s+", " ", cypher_query)
    cypher_query = cypher_query.strip().strip(";") + ";"
    return cypher_query
                     
 
def get_expansion(init_query:str):

    init_query = normalise_query(init_query)

    change_op_match = re.search("(?:CREATE|MERGE|SET|DELETE|REMOVE|DETACH)", init_query)
    if not change_op_match:
        raise RuntimeError("Rule does not contain any state change operation: %s"%init_query)

    condition_part = init_query[:change_op_match.start()]
    effect_part = init_query[change_op_match.start():]

    assignments = []
    for effect_node in re.finditer(NODE_REGEX, effect_part):
        anchor = effect_node.group(1)

        assignments.append("%s:New"%anchor)
        assignments.append("%s.created=CASE WHEN %s.created IS NULL THEN timestamp()"%(anchor, anchor)
                           + " ELSE %s.created END"%(anchor))
        assignments.append("%s.last_updated=timestamp()"%anchor)

        if assignments:
            effect_part = effect_part.strip(";") + " SET " + ", ".join(assignments) + ";"

    return condition_part + effect_part


def focus_on_nodes(init_query:str, node_ids: Set[int]):
    
    init_query = normalise_query(init_query)

    change_op_match = re.search("(?:CREATE|MERGE|SET|DELETE|REMOVE|DETACH|WITH)", init_query)
    if not change_op_match:
        raise RuntimeError("Rule does not contain any state change operation: %s"%init_query)

    condition_part = init_query[:change_op_match.start()]
    effect_part = init_query[change_op_match.start():]

    if len(condition_part) > 0:
        input_node_anchors = set()
        for input_node_match in re.finditer(NODE_REGEX, condition_part):
            input_node_anchors.add(input_node_match.group(1))
        if input_node_anchors:
            id_constraint = "(" + " OR ".join(["id(%s)=%i"%(anchor, node_id) 
                                               for anchor in input_node_anchors
                                               for node_id in node_ids]) + ") "
            where_clause_match = re.search(" WHERE (.+) $", condition_part)
            if where_clause_match:
                new_where = " WHERE (%s) AND %s"%(where_clause_match.group(1), id_constraint)
                condition_part = condition_part[:where_clause_match.start()] + new_where
            else:
                condition_part += "WHERE " + id_constraint
        
    return condition_part + effect_part
import re


def normalise_query(cypher_query:str):
    cypher_query = cypher_query.replace("\n", " ")
    cypher_query = re.sub("\\s+\\)", ")", cypher_query)
    cypher_query =  re.sub("\\s+", " ", cypher_query)
    cypher_query = cypher_query.strip().strip(";") + ";"
    return cypher_query
                     
                     
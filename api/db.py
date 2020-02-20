from tinydb import TinyDB, Query


db = TinyDB('main.json')
db.insert({'int': 1, 'char': 'a'})
db.insert({'int': 1, 'char': 'b'})

print('db init')

def db():
    return db

#User = Query()
# Search for a field value
#db.search(User.name == 'John')
# [{'name': 'John', 'age': 22}, {'name': 'John', 'age': 37}]

# Combine two queries with logical and
#db.search((User.name == 'John') & (User.age <= 30))
# [{'name': 'John', 'age': 22}]

# Combine two queries with logical or
#db.search((User.name == 'John') | (User.name == 'Bob'))
# [{'name': 'John', 'age': 22}, {'name': 'John', 'age': 37}, {'name': 'Bob', 'age': 42}]

# More possible comparisons:  !=  <  >  <=  >=
# More possible checks: where(...).matches(regex), where(...).test(your_test_func)

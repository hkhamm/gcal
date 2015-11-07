# Mongodb Notes

Create/Add user:

3.x: db.createUser({user: "gcal_user", pwd: "apple-pie", roles: 
["readWrite"]})
2.4: db.addUser({user: "gcal_user", pwd: "apple-pie", roles: 
["readWrite"]})


use gcal: switch to db gcal

show users: shows all users
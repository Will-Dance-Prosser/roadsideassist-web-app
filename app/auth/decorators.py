from functools import wraps
from flask import abort
from flask_login import current_user


def role_required(*roles): #Restrict a route to users with one of the specified roles.

    def decorator(f):

        @wraps(f)

        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles: #checks if users role is allowed
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    
    return decorator
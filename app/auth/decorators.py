from functools import wraps
from flask import abort, redirect, url_for
from flask_login import current_user


def role_required(*roles):
    #Restrict a route to users with one of the specified roles.

    def decorator(f):

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login")) #Unauthenticated users are redirected to the login page.
            if current_user.role not in roles:
                abort(403) #Authenticated users whose role is not in the allowed list receive 403.
            return f(*args, **kwargs)
        return decorated_function

    return decorator
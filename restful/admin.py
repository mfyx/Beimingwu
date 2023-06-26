from flask import Blueprint, request
import context
from context import config as C
import hashlib
from .auth import admin_login_required
from .utils import get_parameters, generate_random_str

import lib.database_operations as database

import lib.engine as engine_helper
import flask_jwt_extended
import flask_restful
import flask_bcrypt


admin_blueprint = Blueprint("Admin-API", __name__)
api = flask_restful.Api(admin_blueprint)


class ListUser(flask_restful.Resource):
    @admin_login_required
    def post(self):
        data = request.get_json()
        
        # Get like parameters
        username = None if data is None or "username" not in data else data["username"]
        email    = None if data is None or "email"    not in data else data["email"]
        
        # Return whole user list directly
        if data is None or "limit" not in data:
            ret, cnt = database.get_all_user_list(
                columns=["id", "username", "email"], 
                username=username, 
                email=email
            )
            result = {
                "code": 0,
                "msg": "Get user list success.",
                "data": {"user_list": ret}
            }
            return result, 200
        
        # Calculate the page limit
        limit = data["limit"]
        if limit == 0:
            return {"code": 51, "msg": "Limit cannot be 0."}, 200
        
        page  = 0 if "page" not in data else data["page"]
        
        ret, cnt = database.get_all_user_list(
            columns=["id", "username", "email"], 
            limit=limit, page=page, 
            username=username, email=email
        )
        result = {
            "code": 0,
            "msg": "Get user list success.",
            "data": {
                "user_list": ret,
                "page": page,
                "limit": limit,
                "total_pages": (cnt + limit - 1) // limit
            }
        }
        return result, 200
        pass


class DeleteUser(flask_restful.Resource):
    @admin_login_required
    def post(self):
        # Check & get parameters
        data = request.get_json()

        if data is None or "user_id" not in data:
            return {"code": 21, "msg": "Request parameters error."}, 200
        
        user_id = data["user_id"]

        # Check user existence
        if not database.check_user_exist("id", user_id):
            return {"code": 51, "msg": "User not found."}, 200

        # Check learnware
        ret, cnt = database.get_learnware_list("user_id", user_id)
        if len(ret) > 0:
            learnware_list = engine_helper.get_learnware_by_id([x["learnware_id"] for x in ret])
            return {
                "code": 52, 
                "msg": "Learnware list is not empty.", 
                "data": {
                    "learnware_list": learnware_list
                }
            }, 200

        # Delete user
        cnt = database.remove_user("id", user_id)
        if cnt > 0:
            result = {"code": 0, "msg": "Delete success."}
        else:
            result = {
                "code": 31,
                "msg": "System error.",
            }
        return result, 200
        pass


class ListLearnware(flask_restful.Resource):
    @admin_login_required
    def post(self):
        data = get_parameters(request, [])
        # Return whole user list directly
        if data is None or "limit" not in data:
            ret, cnt = database.get_all_learnware_list(columns=["user_id", "learnware_id", "last_modify"])
            learnware_list = engine_helper.get_learnware_by_id([x["learnware_id"] for x in ret])
            result = {
                "code": 0,
                "msg": "Get learnware list success.",
                "data": {
                    "learnware_list": learnware_list
                }
            }
            return result, 200
        # Calculate the page limit
        limit = data["limit"]
        if limit == 0:
            return {"code": 51, "msg": "Limit cannot be 0."}, 200
        
        page  = 0 if "page" not in data else data["page"]
        ret, cnt = database.get_all_learnware_list(columns=["user_id", "learnware_id", "last_modify"], limit=limit, page=page)
        learnware_list = engine_helper.get_learnware_by_id([x["learnware_id"] for x in ret])
        result = {
            "code": 0,
            "msg": "Get learnware list success.",
            "data": {
                "learnware_list": learnware_list,
                "page": page,
                "limit": limit,
                "total_pages": (cnt + limit - 1) // limit
            }
        }
        return result, 200
    pass


class DeleteLearnware(flask_restful.Resource):
    @admin_login_required
    def post(self):
        # Check & get parameters
        data = request.get_json()
        if data is None or "learnware_id" not in data:
            return {"code": 21, "msg": "Request parameters error."}, 200
        learnware_id = data["learnware_id"]

        # Check permission
        learnware = database.get_learnware_list("learnware_id", learnware_id)
        if len(learnware) == 0:
            return {"code": 51, "msg": "Learnware not found."}, 200

        # Remove learnware
        ret = context.engine.delete_learnware(learnware_id)
        if not ret:
            return {"code": 42, "msg": "Engine delete learnware error."}, 200
        
        database.remove_learnware("learnware_id", learnware_id)

        result = {"code": 0, "msg": "Delete success."}

        return result, 200      
        pass


class ResetPassword(flask_restful.Resource):
    @admin_login_required
    def post(self):
        data = request.get_json()
        if data is None or 'id' not in data: 
            return {"code": 21, "msg": "Request parameters error."}, 200
        
        user_id = data["id"]
        user = database.get_user_info(by="id", value=user_id)
        password = generate_random_str(8)
        md5 = hashlib.md5(password.encode("utf-8")).hexdigest()
        if user is None:
            return {"code": 51, "msg": "Account not exist."}, 200
        
        password_hash = flask_bycrypt.generate_password_hash(password)
        
        flag = database.update_user_password(pwd=password_hash, by="id", value=user_id)
        if not flag:
            return {"code": 31, "msg": "Update error."}, 200
        
        # Return profile
        result = {
            "code": 0,
            "msg": "Reset success",
            "data":{
                "password": password,
                "md5": md5
            }
        }
        return result, 200


api.add_resource(ListUser, "/list_user")
api.add_resource(DeleteUser, "/delete_user")
api.add_resource(ListLearnware, "/list_learnware")
api.add_resource(DeleteLearnware, "/delete_learnware")
api.add_resource(ResetPassword, "/reset_password")



from flask import Blueprint, g, jsonify, request, session
import werkzeug.datastructures
import json
import os
import shutil
from .utils import *

import lib.database_operations as database

import lib.engine as engine_helper
from database.base import LearnwareVerifyStatus
import context
from context import config as C
from . import auth
import flask_jwt_extended
import flask_restx as flask_restful
import flask_bcrypt
import lib.data_utils as data_utils
import uuid
from . import common_functions


user_blueprint = Blueprint("USER-API", __name__)
api = flask_restful.Api(user_blueprint)


class ProfileApi(flask_restful.Resource):
    @flask_jwt_extended.jwt_required()
    def post(self):
        # Return profile
        user_id = flask_jwt_extended.get_jwt_identity()
        user = database.get_user_info(by="id", value=user_id)
        result = {
            "code": 0,
            "msg": "Get profile success.",
            "data": {"username": user["username"], "email": user["email"]},
        }
        return result


class ChangePasswordApi(flask_restful.Resource):
    @flask_jwt_extended.jwt_required()
    def post(self):
        body = request.get_json()
        keys = ["old_password", "new_password"]
        if any([k not in body for k in keys]):
            return {"code": 21, "msg": "Request parameters error."}, 200
        
        old_value = body["old_password"]
        new_value = body["new_password"]

        user_id = flask_jwt_extended.get_jwt_identity()
        print(f'change password for user_id: {user_id}')

        user = database.get_user_info(by="id", value=user_id)

        if user is None:
            return {"code": 51, "msg": "Account not exist."}, 200
        elif not flask_bcrypt.check_password_hash(user["password"], old_value):
            return {"code": 52, "msg": "Incorrect password."}, 200
        
        new_passwd_hash = flask_bcrypt.generate_password_hash(new_value).decode("utf-8")
        flag = database.update_user_password(
            pwd=new_passwd_hash, by="id", value=user_id)
        
        if not flag:
            return {"code": 31, "msg": "Update error."}, 200

        # Return profile
        result = {"code": 0, "msg": "Update success"}
        return result, 200
    pass


class ListLearnwareApi(flask_restful.Resource):
    @flask_jwt_extended.jwt_required()
    def post(self):
        body = request.get_json()
        keys = ["limit", "page"]
        if any([k not in body for k in keys]):
            return {"code": 21, "msg": "Request parameters error."}, 200
        
        limit = body["limit"]
        page = body["page"]

        user_id = flask_jwt_extended.get_jwt_identity()
        # ret, cnt = database.get_learnware_list("user_id", user_id, limit=limit, page=page, is_verified=True)
        rows, cnt = database.get_learnware_list_by_user_id(user_id, limit=limit, page=page)

        learnware_list = []
        for row in rows:
            learnware_info = dict()
            learnware_info["learnware_id"] = row["learnware_id"]
            learnware_info["last_modify"] = row["last_modify"].strftime("%Y-%m-%d %H:%M:%S.%f %Z")
            learnware_info["verify_status"] = row["verify_status"]

            learnware_info["semantic_specification"] = data_utils.get_learnware_semantic_specification(
                learnware_info)
            print(f'learnware_id: {learnware_info["learnware_id"]}, semantic_specification: {learnware_info["semantic_specification"]}')

            learnware_list.append(learnware_info)
            
        result = {
            "code": 0,
            "msg": "Ok.",
            "data": {
                "learnware_list": learnware_list,
                "page": page,
                "limit": limit,
                "total_pages": (cnt + limit - 1) // limit
            }
        }
        return result, 200
    pass


class ListLearnwareUnverifiedApi(flask_restful.Resource):
    @flask_jwt_extended.jwt_required()
    def post(self):
        body = request.get_json()
        keys = ["limit", "page"]
        if any([k not in body for k in keys]):
            return {"code": 21, "msg": "Request parameters error."}, 200
        
        limit = body["limit"]
        page = body["page"]

        user_id = flask_jwt_extended.get_jwt_identity()
        ret, cnt = database.get_learnware_list("user_id", user_id, limit=limit, page=page, is_verified=False)

        # read semantic specification
        learnware_list = []
        for row in ret:
            learnware_id = row["learnware_id"]
            learnware_info = dict()
            semantic_spec_path = context.get_learnware_verify_file_path(learnware_id)[:-4] + ".json"
            with open(semantic_spec_path, "r") as f:
                learnware_info["semantic_specification"] = json.load(f)
                pass
            learnware_info["learnware_id"] = learnware_id
            learnware_list.append(learnware_info)
            pass
        

        result = {
            "code": 0,
            "msg": "Ok.",
            "data": {
                "learnware_list": learnware_list,
                "page": page,
                "limit": limit,
                "total_pages": (cnt + limit - 1) // limit
            }
        }
        return result, 200        


class AddLearnwareApi(flask_restful.Resource):
    @flask_jwt_extended.jwt_required()
    def post(self):
        semantic_specification_str = request.form.get("semantic_specification")

        print(semantic_specification_str)
        semantic_specification, err_msg = engine_helper.parse_semantic_specification(semantic_specification_str)
        if semantic_specification is None:
            return {"code": 41, "msg": err_msg}, 200
        
        learnware_file = request.files.get("learnware_file")
        if learnware_file is None or learnware_file.filename == "":
            return {"code": 21, "msg": "Request parameters error."}, 200
        
        learnware_id = database.get_next_learnware_id()

        if not os.path.exists(C.upload_path):
            os.mkdir(C.upload_path)

        learnware_path = context.get_learnware_verify_file_path(learnware_id)

        learnware_file.seek(0)
        learnware_file.save(learnware_path)

        result, retcd = common_functions.add_learnware(
            learnware_path, semantic_specification, learnware_id)
        
        return result, retcd
    pass


parser_update_learnware = flask_restful.reqparse.RequestParser()
parser_update_learnware.add_argument("learnware_id", type=str, required=True, location="form")
parser_update_learnware.add_argument("semantic_specification", type=str, required=True, location="form")
parser_update_learnware.add_argument("learnware_file", type=werkzeug.datastructures.FileStorage, location="files")
class UpdateLearnwareApi(flask_restful.Resource):
    @api.expect(parser_update_learnware)
    @flask_jwt_extended.jwt_required()
    def post(self):
        semantic_specification_str = request.form.get("semantic_specification")
        learnware_id = request.form.get("learnware_id")

        print(semantic_specification_str)
        semantic_specification, err_msg = engine_helper.parse_semantic_specification(semantic_specification_str)
        if semantic_specification is None:
            return {"code": 41, "msg": err_msg}, 200
        
        verify_status = database.get_learnware_verify_status(learnware_id)

        if verify_status == LearnwareVerifyStatus.PROCESSING.value:
            return {"code": 51, "msg": "Learnware is verifying."}, 200
        
        learnware_file = None
        if request.files is not None:
            learnware_file = request.files.get("learnware_file")
            pass

        learnware_path = context.get_learnware_verify_file_path(learnware_id)
        learnware_semantic_spec_path = learnware_path[:-4] + ".json"
        with open(learnware_semantic_spec_path, "w") as f:
            json.dump(semantic_specification, f)
            pass
        if learnware_file is not None:
            learnware_file.seek(0)
            learnware_file.save(learnware_path)
            pass
        
        database.update_learnware_timestamp(learnware_id)

        if verify_status == LearnwareVerifyStatus.SUCCESS.value:
            # this learnware is verified
            print(f'update verified learnware: {learnware_id}')

            if learnware_file is None:
                learnware_path_origin = context.engine.get_learnware_path_by_ids(learnware_id)
                shutil.copyfile(learnware_path_origin, learnware_path)
                pass
            context.engine.delete_learnware(learnware_id)
            database.update_learnware_verify_result(learnware_id, LearnwareVerifyStatus.WAITING, "")
            pass
        elif verify_status == LearnwareVerifyStatus.FAIL.value:
            # this learnware is failed
            print(f'update failed learnware: {learnware_id}')
            database.update_learnware_verify_result(learnware_id, LearnwareVerifyStatus.WAITING, "")
            pass
        else:
            pass
        
        
        return {"code": 0, "msg": "success"}, 200
        

class AddLearnwareVerifiedApi(flask_restful.Resource):
    # todo: this api should be protected
    def post(self):
        body = request.get_json()

        learnware_id = body["learnware_id"]
        learnware_file = context.get_learnware_verify_file_path(learnware_id)
        learnware_file_processed = learnware_file[:-4] + "_processed.zip"
        learnware_semantic_spec_path = learnware_file[:-4] + ".json"

        with open(learnware_semantic_spec_path, "r") as f:
            semantic_specification = json.load(f)
            pass
        
        context.engine.add_learnware(learnware_file_processed, semantic_specification, learnware_id=learnware_id)

        return {"code": 0, "msg": "success"}, 200
    pass


class DeleteLearnwareApi(flask_restful.Resource):
    @flask_jwt_extended.jwt_required()
    def post(self):
        body = request.get_json()
        learnware_id= body.get("learnware_id")
        
        if learnware_id is None:
            return {"code": 21, "msg": "Request parameters error."}, 200
        
        learnware_id = body["learnware_id"]
        user_id = flask_jwt_extended.get_jwt_identity()

        if database.check_user_admin(user_id):
            user_id = database.get_user_id_by_learnware(learnware_id)
            pass

        return common_functions.delete_learnware(user_id, learnware_id)
    pass


@api.doc(params={'learnware_id': 'learnware id'})
class VerifyLog(flask_restful.Resource):
    @flask_jwt_extended.jwt_required()
    def get(self):
        user_id = flask_jwt_extended.get_jwt_identity()
        learnware_id = request.args.get("learnware_id")

        # check if user is admin
        if database.check_user_admin(user_id):
            user_id = database.get_user_id_by_learnware(learnware_id)
            pass

        result = database.get_verify_log(user_id, learnware_id)

        return {"code": 0, "data": result}, 200
    pass


@api.route("/create_token")
class CreateToken(flask_restful.Resource):
    @flask_jwt_extended.jwt_required()
    def post(self):
        user_id = flask_jwt_extended.get_jwt_identity()
        token = uuid.uuid4().hex

        database.create_user_token(user_id, token)

        return {"code": 0, "data": {"token": token}}, 200
    pass


@api.route("/list_token")
class ListToken(flask_restful.Resource):
    @flask_jwt_extended.jwt_required()
    def post(self):
        user_id = flask_jwt_extended.get_jwt_identity()

        result = database.get_user_tokens(user_id)

        result = {
            "token_list": result
        }

        return {"code": 0, "data": result}, 200
    pass


delete_token_parser = flask_restful.reqparse.RequestParser()
delete_token_parser.add_argument("token", type=str, required=True, help="token", location="json")
@api.route("/delete_token")
class DeleteToken(flask_restful.Resource):
    @api.expect(delete_token_parser)
    @flask_jwt_extended.jwt_required()
    def post(self):
        user_id = flask_jwt_extended.get_jwt_identity()
        token = request.get_json().get("token")

        if token is None:
            return {"code": 21, "msg": "Request parameters error."}, 200

        database.delete_user_token(user_id, token)

        return {"code": 0, "msg": "success"}, 200
    pass


parser_chunked_upload = flask_restful.reqparse.RequestParser()
parser_chunked_upload.add_argument("chunk_begin", type=int, required=True, location="form")
parser_chunked_upload.add_argument("file_hash", type=str, required=True, location="form")
parser_chunked_upload.add_argument("chunk_file", type=werkzeug.datastructures.FileStorage, location="files")
@api.route("/chunked_upload")
class ChunkedUpload(flask_restful.Resource):
    @flask_jwt_extended.jwt_required()
    @api.expect(parser_chunked_upload)
    def post(self):
        file = request.files["chunk_file"]
        file_hash = request.form["file_hash"]
        chunk_begin = int(request.form["chunk_begin"])
        file_path = os.path.join(context.config.upload_path, file_hash)
        
        os.makedirs(context.config.upload_path, exist_ok=True)

        with open(file_path, "ab+") as fout:
            fout.seek(chunk_begin)
            fout.write(file.stream.read())
            pass

        return {"code": 0, "msg": "success"}, 200


parser_add_learnware_uploaded = flask_restful.reqparse.RequestParser()
parser_add_learnware_uploaded.add_argument("file_hash", type=str, location="json")
parser_add_learnware_uploaded.add_argument("semantic_specifiction", type=str, location="json")
@api.route("/add_learnware_uploaded")
class AddLearnwareUploaded(flask_restful.Resource):
    @flask_jwt_extended.jwt_required()
    @api.expect(parser_add_learnware_uploaded)
    def post(self):
        body = request.get_json()
        semantic_specification_str = body.get("semantic_specification")

        semantic_specification, err_msg = engine_helper.parse_semantic_specification(
            semantic_specification_str)
        if semantic_specification is None:
            return {"code": 41, "msg": err_msg}, 200
        
        learnware_id = database.get_next_learnware_id()
        src_file_path = os.path.join(context.config.upload_path, body["file_hash"])
        dst_file_path = context.get_learnware_verify_file_path(learnware_id)

        os.rename(src_file_path, dst_file_path)
        learnware_path = dst_file_path
        
        result, retcd = common_functions.add_learnware(
            learnware_path, semantic_specification, learnware_id)
        
        return result, retcd

api.add_resource(ProfileApi, "/profile")
api.add_resource(ChangePasswordApi, "/change_password")
api.add_resource(ListLearnwareApi, "/list_learnware")
api.add_resource(ListLearnwareUnverifiedApi, "/list_learnware_unverified")
api.add_resource(AddLearnwareApi, "/add_learnware")
api.add_resource(UpdateLearnwareApi, "/update_learnware")
api.add_resource(AddLearnwareVerifiedApi, "/add_learnware_verified")
api.add_resource(DeleteLearnwareApi, "/delete_learnware")
api.add_resource(VerifyLog, "/verify_log")

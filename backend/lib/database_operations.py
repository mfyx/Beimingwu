from typing import Tuple
from datetime import datetime
import context
import database.base
from database.base import LearnwareVerifyStatus


def convert_datetime(v) -> datetime:
    if isinstance(v, datetime):
        pass
    elif isinstance(v, str):
        v = datetime.strptime(v, "%Y-%m-%d %H:%M:%S.%f")
        pass
    else:
        raise Exception("Unknown datetime format.")
    
    local_tz = datetime.now().astimezone().tzinfo
    v = v.replace(tzinfo=local_tz)
    
    return v
    

def check_user_exist(by, value, conn=None):
    rows = context.database.execute(f"SELECT {by} FROM tb_user WHERE {by} = :{by}", {by: value}, conn=conn)

    if len(rows) == 0:
        return False
    else:
        return True


def get_user_info(by, value):
    rows = context.database.execute(f"SELECT * FROM tb_user WHERE {by} = :{by}", {by: value})
    if len(rows) == 0:
        return None
    else:
        return rows[0]._mapping


def update_user_password(by, value, pwd):
    context.database.execute(
        f"UPDATE tb_user SET password = :password WHERE {by} = :{by}", 
        {"password": pwd, by: value})
    return True


def add_user(username, password, email, role, nickname, conn=None):
    rows = context.database.execute(
        'INSERT INTO tb_user (username, password, email, role, nickname, register) VALUES (:username, :password, :email, :role, :nickname, :register) RETURNING id',
        {
            'username': username, 
            'password': password, 
            'email': email,
            'role': role,
            'nickname': nickname,
            'register': datetime.now()
        },
        conn=conn
    )
    return rows[0][0]


def register_user(username, password, email) -> Tuple[int, str]:
    '''all db ops in register user should in a session
    '''
    
    with begin() as conn:
        user_info= get_user_info(by="email", value=email)

        if user_info is None:
            # email not exist

            # Check uniqueness of username
            if check_user_exist(by="username", value=username, conn=conn):
                return 51, "Username already exist.", -1

            user_id = add_user(username, password, email, 0, username, conn=conn)

            if user_id is None:
                return 31, "System error.", -1
                pass
            conn.commit()

            return 0, 'success', user_id
            pass
        else:
            # email exist

            # Check uniqueness of email
            if user_info['email_confirm_time'] is not None:
                return 52, "Email already exist.", -1
            else:
                # email not verified
                return 53, "Email not verified.", -1
            pass
        pass
    pass


def update_email_confirm_time(email, dtime=None):
    if dtime is None:
        dtime = datetime.now()
        pass

    context.database.execute(
        "UPDATE tb_user SET email_confirm_time = :dtime WHERE email = :email",
        {"dtime": dtime, "email": email}
    )

    pass


def get_all_learnware_list(columns, limit=None, page=None, is_verified=None, user_id=None):
    column_str = ", ".join(columns)

    if is_verified is None:
        where = ""
    elif is_verified:
        where = "WHERE verify_status = :verify_status "
    else:
        where = "WHERE verify_status <> :verify_status "

    if user_id is not None:
        if is_verified is None:
            where = "WHERE user_id = :user_id"
        else:
            where += "AND user_id = :user_id"

    count = context.database.execute(
        f"SELECT COUNT(1) FROM tb_user_learnware_relation {where}",
        {"verify_status": LearnwareVerifyStatus.SUCCESS.value, "user_id": user_id})
    
    suffix = "" if limit is None or page is None else f"LIMIT {limit} OFFSET {limit * page}"
    query = f"""
        SELECT {column_str}
        FROM tb_user_learnware_relation
        {where}
        ORDER BY 
            CASE 
                WHEN verify_status = :verify_FAIL THEN 0
                WHEN verify_status = :verify_WAITING THEN 1
                WHEN verify_status = :verify_PROCESSING THEN 2
                WHEN verify_status = :verify_QUEUE THEN 3
                ELSE 4
            END, 
            learnware_id DESC
        {suffix}
    """
    ret = context.database.execute(query, {
        "user_id": user_id,
        "verify_FAIL": LearnwareVerifyStatus.FAIL.value,
        "verify_WAITING": LearnwareVerifyStatus.WAITING.value,
        "verify_PROCESSING": LearnwareVerifyStatus.PROCESSING.value,
        "verify_QUEUE": LearnwareVerifyStatus.QUEUE.value,
        "verify_status": LearnwareVerifyStatus.SUCCESS.value
    })
    
    results = []
    for row in ret:
        r = dict(zip(columns, row))
        r["last_modify"] = convert_datetime(r["last_modify"])
        results.append(r)
        pass

    return results, count[0][0]

def get_learnware_list(by, value, limit=None, page=None, is_verified=None):

    sql = f"FROM tb_user_learnware_relation WHERE {by} = :{by}"
    if is_verified is None:
        pass
    elif is_verified:
        sql += " AND verify_status = :verify_status "
    else:
        sql += " AND verify_status <> :verify_status "
        pass

    cnt = context.database.execute(
        "SELECT COUNT(1) " + sql, 
        {by: value, "verify_status": LearnwareVerifyStatus.SUCCESS.value})

    suffix = "" if limit is None or page is None else f"LIMIT {limit} OFFSET {limit * page}"

    order = " ORDER BY learnware_id DESC "    
    rows = context.database.execute(
        "SELECT * " + sql + order + suffix,
        {by: value, "verify_status": LearnwareVerifyStatus.SUCCESS.value})
    
    return [r._mapping for r in rows], cnt[0][0]


def get_learnware_list_by_user_id(user_id, limit, page):
    cnt = context.database.execute(
        "SELECT COUNT(1) FROM tb_user_learnware_relation WHERE user_id = :user_id",
        {"user_id": user_id}
    )[0][0]

    query = """
        SELECT learnware_id, last_modify, verify_status
        FROM tb_user_learnware_relation
        WHERE user_id = :user_id
        ORDER BY 
            CASE 
                WHEN verify_status = :verify_FAIL THEN 0
                WHEN verify_status = :verify_WAITING THEN 1
                WHEN verify_status = :verify_PROCESSING THEN 2
                WHEN verify_status = :verify_QUEUE THEN 3
                ELSE 4
            END, 
            learnware_id DESC
        LIMIT :limit
        OFFSET :offset
    """
    rows = context.database.execute(query, {
        "user_id": user_id, "limit": limit, "offset": limit * page,
        "verify_FAIL": LearnwareVerifyStatus.FAIL.value,
        "verify_WAITING": LearnwareVerifyStatus.WAITING.value,
        "verify_PROCESSING": LearnwareVerifyStatus.PROCESSING.value,
        "verify_QUEUE": LearnwareVerifyStatus.QUEUE.value,
    })
    
    rows_ = []
    for row in rows:
        row_ = dict()
        for k, v in row._mapping.items():
            if k == "last_modify":
                row_[k] = convert_datetime(v)
                pass
            else:
                row_[k] = v
                pass
            pass
        rows_.append(row_)
        pass

    return rows_, cnt


def get_verify_log(user_id, learnware_id):
    rows = context.database.execute(
        "SELECT verify_log FROM tb_user_learnware_relation WHERE user_id = :user_id AND learnware_id = :learnware_id",
        {"user_id": user_id, "learnware_id": learnware_id}
    )
    
    if len(rows) == 0:
        return None
    
    return rows[0][0]


def get_learnware_by_learnware_id(learnware_id):
    rows = context.database.execute(
        "SELECT learnware_id, last_modify, verify_status FROM tb_user_learnware_relation WHERE learnware_id = :learnware_id",
        {"learnware_id": learnware_id}
    )
    
    if len(rows) == 0:
        return None
    
    learnware_info = {k:v for k, v in rows[0]._mapping.items()}
    learnware_info["last_modify"] = convert_datetime(learnware_info["last_modify"]).strftime("%Y-%m-%d %H:%M:%S.%f %Z")
    
    return learnware_info

def add_learnware(user_id, learnware_id):
    context.database.execute(
        'INSERT INTO tb_user_learnware_relation (user_id, learnware_id, last_modify) VALUES(:user_id, :learnware_id, :last_modify)',
        {'user_id': user_id, 'learnware_id': learnware_id, 'last_modify': datetime.now()}
    )
    return 1


def get_learnware_owner(learnware_id):
    rows = context.database.execute(
        "SELECT username FROM tb_user WHERE id IN (SELECT user_id FROM tb_user_learnware_relation WHERE learnware_id = :learnware_id)",
        {"learnware_id": learnware_id}
    )
    if len(rows) == 0 or len(rows[0]) == 0: 
        return "Unknown"
    return rows[0][0]


def remove_learnware(by, value):
    context.database.execute(f"DELETE FROM tb_user_learnware_relation WHERE {by} = :{by}",
                     {by: value})
    return 1


def remove_user(by, value):
    context.database.execute(
        f"DELETE FROM tb_user WHERE {by} = :{by}",
        {by: value})
    return 1


def get_all_user_list(columns, limit=None, page=None, username=None, email=None):
    column_str = ", ".join(columns)
    cnt = context.database.execute(f"SELECT COUNT(*) FROM tb_user")

    query = f"""
        SELECT
            {column_str},
            COUNT(CASE WHEN tb_user_learnware_relation.verify_status = :verify_status THEN 1 END) AS verified_learnware_count,
            COUNT(CASE WHEN tb_user_learnware_relation.verify_status <> :verify_status THEN 1 END) AS unverified_learnware_count
        FROM
            tb_user
        LEFT JOIN
            tb_user_learnware_relation ON tb_user.id = tb_user_learnware_relation.user_id
    """
    
    like_suffix = ""
    group_suffix = f"GROUP BY {column_str}"
    if username is not None or email is not None:
        if username is None or email is None:
            like_suffix = "WHERE "
            if username is not None: like_suffix += f"username LIKE '%{username}%'"
            if email is not None: like_suffix += f"email LIKE '%{email}%'"
        else:
            like_suffix = f"WHERE username LIKE '%{username}%' AND email LIKE '%{email}%'"
    page_suffix = "" if limit is None or page is None else f"LIMIT {limit} OFFSET {limit * page}"
    rows = context.database.execute(f"{query} {like_suffix} {group_suffix} {page_suffix}", {"verify_status": LearnwareVerifyStatus.SUCCESS.value})
    results = [dict(zip(columns + ["verified_learnware_count", "unverified_learnware_count"], user)) for user in rows]
    
    return results, cnt[0][0]


def get_next_learnware_id():
    result = context.database.execute("UPDATE tb_global_counter set value = value + 1 WHERE name = 'learnware_id' RETURNING value")
    print(result)
    value = result[0][0]

    return f'{value:08d}'


def check_learnware_exist(learnware_id: str):
    result = context.database.execute(
        "SELECT COUNT(1) FROM tb_user_learnware_relation WHERE learnware_id = :learnware_id",
        {"learnware_id": learnware_id}
    )

    return result[0][0] > 0


def get_unverified_learnware():
    result = context.database.execute(
        "SELECT learnware_id FROM tb_user_learnware_relation WHERE verify_status = :status",
        {"status": LearnwareVerifyStatus.WAITING.value})
    
    return [r[0] for r in result]


def update_learnware_timestamp(learnware_id, timestamp: datetime = None):
    if timestamp is None:
        timestamp = datetime.now()
        pass

    context.logger.info(f'update learnware timestamp: {learnware_id}, {timestamp}')
    
    context.database.execute(
        "UPDATE tb_user_learnware_relation SET last_modify = :now WHERE learnware_id = :learnware_id",
        {"now": timestamp, "learnware_id": learnware_id}
    )
    pass


def get_learnware_timestamp(learnware_id):
    result = context.database.execute(
        "SELECT last_modify FROM tb_user_learnware_relation WHERE learnware_id = :learnware_id",
        {"learnware_id": learnware_id}
    )
    if len(result) == 0:
        return datetime.strptime("2021-01-01", "%Y-%m-%d")
    
    return convert_datetime(result[0][0])


def update_learnware_verify_status(learnware_id, status: LearnwareVerifyStatus):
    context.database.execute(
        "UPDATE tb_user_learnware_relation SET verify_status = :status WHERE learnware_id = :learnware_id",
        {"status": status.value, "learnware_id": learnware_id}
    )
    pass


def update_learnware_verify_result(learnware_id, status: LearnwareVerifyStatus, verify_log: str):
    if len(verify_log) > 30000:
        verify_log = verify_log[-30000:]
        pass
    
    context.database.execute(
        "UPDATE tb_user_learnware_relation SET verify_status = :status, verify_log = :verify_log WHERE learnware_id = :learnware_id",
        {"status": status.value, "learnware_id": learnware_id, "verify_log": verify_log}
    )


def reset_learnware_verify_status():
    context.database.execute(
        "UPDATE tb_user_learnware_relation SET verify_status = :waiting WHERE verify_status = :processing OR verify_status = :waiting_queue",
        {
            "processing": LearnwareVerifyStatus.PROCESSING.value, 
            "waiting": LearnwareVerifyStatus.WAITING.value, 
            "waiting_queue": LearnwareVerifyStatus.QUEUE.value
        }
    )


def get_learnware_verify_status(learnware_id):
    result = context.database.execute(
        "SELECT verify_status FROM tb_user_learnware_relation WHERE learnware_id = :learnware_id",
        {"learnware_id": learnware_id}
    )
    if len(result) == 0:
        raise RuntimeError(f"learnware_id {learnware_id} not found")
    
    return result[0][0]


def create_user_token(user_id, token):
    context.database.execute(
        "INSERT INTO tb_user_token (user_id, token) VALUES (:user_id, :token)",
        {"user_id": user_id, "token": token}
    )
    pass


def get_user_tokens(user_id) -> list[str]:
    result = context.database.execute(
        "SELECT token FROM tb_user_token WHERE user_id = :user_id",
        {"user_id": user_id}
    )
    if len(result) == 0:
        return []
    
    tokens = []
    for row in result:
        tokens.append(row[0])
        pass
    return tokens


def delete_user_token(user_id, token):
    context.database.execute(
        "DELETE FROM tb_user_token WHERE user_id = :user_id AND token = :token",
        {"user_id": user_id, "token": token}
    )
    pass

def add_log(name, info):
    context.database.execute(
        "INSERT INTO tb_log (create_time, name, info) VALUES (:create_time, :name, :info)",
        {"create_time": datetime.now(), "name": name, "info": info}
    )
    pass

def get_user_count():
    result = context.database.execute(
        "SELECT COUNT(1) FROM tb_user"
    )
    return result[0][0]


def get_learnware_count_verified():
    result = context.database.execute(
        "SELECT COUNT(1) FROM tb_user_learnware_relation WHERE verify_status = :verify_status",
        {"verify_status": LearnwareVerifyStatus.SUCCESS.value}
    )
    return result[0][0]
    pass


def get_learnware_count_unverified():
    result = context.database.execute(
        "SELECT COUNT(1) FROM tb_user_learnware_relation WHERE verify_status <> :verify_status",
        {"verify_status": LearnwareVerifyStatus.SUCCESS.value}
    )
    return result[0][0]
    pass


def get_download_count():
    result = context.database.execute(
        "SELECT COUNT(1) FROM tb_log WHERE name = 'download_learnware'"
    )
    return result[0][0]
    pass


def check_user_admin(user_id):
    result = context.database.execute(
        "SELECT role FROM tb_user WHERE id = :user_id",
        {"user_id": user_id}
    )

    if len(result) == 0:
        return False
    
    return result[0][0] == 1


def get_user_id_by_learnware(learnware_id):
    result = context.database.execute(
        "SELECT user_id FROM tb_user_learnware_relation WHERE learnware_id = :learnware_id",
        {"learnware_id": learnware_id}
    )
    if len(result) == 0:
        return None
    
    return result[0][0]

def begin():
    return context.database.begin()
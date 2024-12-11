from fastapi import FastAPI, WebSocket
import asyncio

from database import Database


class UserDatabase(Database):
    def __init__(self):
        super().__init__("storm_stream", "user_data")
        self.time_collection = self.db["user_time"]
        self.user_id = "shashstorm"

    async def get_data(self, title):
        dt = await self.collection.find_one(
            {"user_id": self.user_id, "title": title}
        )
        if dt:
            dt.pop("_id", "")
        return dt

    async def update_data(self, data):
        await self.save_time(data)
        await self.collection.update_one(
            {"user_id": self.user_id, "title": data["title"]},
            {"$set": data},
            upsert=True
        )
        return True

    async def save_time(self, data):
        if not data.get("time") or not data.get("episode") or not data.get("episode").get("name"):
            return {"error": "Missing required fields"}
        await self.time_collection.update_one(
            {"user_id": self.user_id, "title": data["title"], "episode.name": data["episode"]["name"]},
            {"$set": {"time": data["time"]}},
            upsert=True
        )
        return True

    async def get_time(self, episode_id):
        try:
            return (await self.collection.find_one(
                {"user_id": self.user_id, "episode_id": episode_id}
            ))["time"]
        except TypeError:
            return 0


def add_user_datastorage(app: FastAPI):
    user_db = UserDatabase()

    @app.post("/userdata/stream_state")
    async def stream_state(data: dict):
        update_result = await user_db.update_data(data["data"])
        return update_result

    @app.get("/userdata/stream_state")
    async def stream_state(title: str):
        data = await user_db.get_data(title)
        return data

    @app.get("/userdata/stream_time")
    async def stream_state(episode_id: str):
        data = await user_db.get_time(episode_id)
        return {"time": int(data)}

    return user_db

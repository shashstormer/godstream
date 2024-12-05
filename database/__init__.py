import re

from motor.motor_asyncio import AsyncIOMotorClient
from config import Config


class Database:
    def __init__(self, db_name, collection_name):
        """
        Initialize the Database instance.

        :param db_name: Name of the MongoDB database.
        :param collection_name: Name of the collection within the database.
        """
        self.client = AsyncIOMotorClient(Config.mongo_url)  # Initialize the MongoDB client.
        self.db = self.client[db_name]  # Select the database.
        self.collection = self.db[collection_name]  # Select the collection.

    async def title(self, title):
        """
        Find documents in the collection whose `titles` field starts with or contains the specified title.
        If `titles` starts with the given title, insert the document at the beginning of the result list.
        If `titles` contains the given title, append the document to the end of the result list.

        :param title: The title to search for.
        :return: A sorted list of matching documents.
        """
        starts_with = []
        contains = []
        # Correct MongoDB query with $regex
        async for document in self.collection.find({"titles": {"$regex": re.escape(title), "$options": "i"}}):
            titles = document.get('titles', [])
            if any(t.startswith(title) for t in titles):
                starts_with.insert(0, document)
            elif any(title in t for t in titles):
                contains.append(document)
        async for document in self.collection.find({"title": {"$regex": re.escape(title), "$options": "i"}}):
            titles = document.get('titles', [])
            if any(t.startswith(title) for t in titles):
                starts_with.insert(0, document)
            elif any(title in t for t in titles):
                contains.append(document)
        return starts_with + contains

    async def update_title(self, title, data):
        """
        Update documents in the collection where any title in the `titles` field matches the specified title exactly.
        Replace the matching document with the provided data.

        :param title: The title to search for.
        :param data: The data to update the matching document with.
        :return: The count of documents updated.
        """
        # Find documents where the `titles` array contains the exact title.
        filter_query = {'titles': title}  # MongoDB query for absolute match in the array.
        result = await self.collection.update_many(filter_query, {'$set': data}, upsert=True)
        return result.modified_count

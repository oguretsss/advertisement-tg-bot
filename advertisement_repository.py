import logging


class Advertisement:
    def __init__(self, user_id, caption):
        self.user_id = user_id
        self.caption = caption
        self.media = []

    def add_media(self, file_id):
        self.media.append(file_id)


class AdvertisementRepository:
    def __init__(self):
        self.active_advertisements = {}

    def add_advertisement(self, user_id, caption, username=None, first_name=None, last_name=None):
        self.active_advertisements[user_id] = Advertisement(user_id, caption)

    def remove_advertisement(self, user_id):
        try:
            del self.active_advertisements[user_id]
        except KeyError:
            logging.error(f"Cannot delete advertisement for user: {user_id}. Not found among active advertisements:")
            logging.error(f"{self.active_advertisements}")


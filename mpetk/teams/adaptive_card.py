import re
from typing import List, Tuple


class AdaptiveCard:
    def __init__(self, title: str):
        self.json = self.get_adaptive_card_object()
        self.content = self.json['attachments'][0]['content']
        self.body = self.json['attachments'][0]['content']['body']
        self.actions = None

        self.add_title(title)

    def __str__(self):
        return self.json

    @staticmethod
    def get_adaptive_card_object():
        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": 'null',
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.0",
                        "msteams": {
                            "width": "full"
                        },
                        "body": [],
                    }
                }
            ]
        }

    def add_description(self, text: str) -> None:
        self.body.extend([
            {
                "type": "TextBlock",
                "text": "Description ",
                "spacing": "extraLarge"
            },
            {
                "type": "Container",
                "style": "emphasis",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": text
                    }
                ]
            }
        ])

    def add_link_button(self, link: Tuple) -> None:
        link = [
            {
                "type": "Action.OpenUrl",
                "title": link[0],
                "url": link[1]
            }
        ]
        if self.actions is not None:
            self.actions.extend(link)
        else:
            self.content['actions'] = link
            self.actions = self.content['actions']

    def add_log_info(self, rig_id: str, log_link: str) -> None:
        self.body.extend([
            {
                "type": "TextBlock",
                "text": "Log Info ",
                "spacing": "extraLarge"
            },
            {
                "type": "Container",
                "style": "emphasis",
                "items": [
                    {
                        "type": "RichTextBlock",
                        "inlines": [
                            {
                                "type": "TextRun",
                                "text": "rigID:   ",
                                "weight": "bolder"
                            },
                            {
                                "type": "TextRun",
                                "text": rig_id
                            }
                        ]
                    },
                    {
                        "type": "RichTextBlock",
                        "inlines": [
                            {
                                "type": "TextRun",
                                "text": "log link:   ",
                                "weight": "bolder"
                            },
                            {
                                "type": "TextRun",
                                "text": log_link
                            }
                        ]
                    }
                ]
            }
        ])

    def add_tags(self, tags: List[str]) -> None:
        regex = r'\b[A-Za-z0-9._%+-]+@alleninstitute\.org\b'

        tags_text = ""
        for tag in tags:
            if re.fullmatch(regex, tag):
                tags_text += f"<at>{tag}</at> "

        if tags_text != "":
            self.body.extend([
                {
                    "type": "TextBlock",
                    "text": tags_text
                }
            ])

    def add_title(self, text: str) -> None:
        self.body.extend([
            {
                "type": "TextBlock",
                "text": text,
                "style": "heading",
                "size": "extraLarge"
            }
        ])


# Thoses emoji are mostly used in Spectrum, but arent recoginzed
# by the emoji python lib, those small helpers will handle the conversion
import logging
import re

import emoji

logger = logging.getLogger('bot.EmojiMapper')


class EmojiMapper:
    """ Thoses emoji are mostly used in Spectrum, but arent recognized
    by the emoji python lib, this small helper class will handle the conversion.
    """

    def __init__(self):
        self.emoji_regex = re.compile(r":[0-9a-z]+(?:_[0-9a-z]+)*:", re.MULTILINE)
        self.aliases_map = {
            ':first_place_medal:': ':1st_place_medal:',
            ':second_place_medal:': ':2nd_place_medal:',
            ':third_place_medal:': ':3rd_place_medal:',
        }

    def get_patchable_shortcodes(self, shortcodes):
        return [sc for sc in shortcodes if sc in self.aliases_map.keys()]

    def _replace_emoji_shortcodes(self, text):

        emojis_shortcodes = set(self.emoji_regex.findall(text))
        emojis_shortcodes_to_patch = self.get_patchable_shortcodes(emojis_shortcodes)

        for shortcode in emojis_shortcodes_to_patch:
            shortcode_converted = self.aliases_map[shortcode]
            text = text.replace(shortcode, shortcode_converted)
            logger.info(f"{shortcode} -> {shortcode_converted}")

        text_emojized = emoji.emojize(text, language='alias')

        unsupported_shortcodes = set(self.emoji_regex.findall(text_emojized))
        if unsupported_shortcodes:
            logger.warning(f"Unsupported Emojis detected: {unsupported_shortcodes}")

        return text_emojized

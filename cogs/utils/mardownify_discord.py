import re
from markdownify import MarkdownConverter
from textwrap import fill

line_beginning_re = re.compile(r'^', re.MULTILINE)

UNDERLINED = 'underlined'

class DiscordMarkdownConverted(MarkdownConverter):
    """
    Overrides to ensure the markdown result is properly handled by discord
    """

    def convert_hn(self, n, el, text, convert_as_inline):
        """
        '#' Syntax is not supported by Discord
        """
        if convert_as_inline:
            return text

        style = self.options['heading_style'].lower()
        text = text.rstrip()
        if style == UNDERLINED and n <= 2:
            return f'**__{text}__**\n\n'

        return f'**{text}**\n\n'

    def convert_p(self, el, text, convert_as_inline):
        """
        empty <p> are used as new line in sources HTML
        """
        if convert_as_inline:
            return text
        if self.options['wrap']:
            text = fill(text,
                        width=self.options['wrap_width'],
                        break_long_words=False,
                        break_on_hyphens=False)
        return f'{text}\n\n' if text else '\n'

    def convert_blockquote(self, el, text, convert_as_inline):
        """
        Strip any text at the end of blockquotes
        """

        if convert_as_inline:
            return text

        return '\n' + (line_beginning_re.sub('> ', text.rstrip()) + '\n\n') if text else ''

def markdownify(soup, **options):
    return DiscordMarkdownConverted(**options).convert_soup(soup)

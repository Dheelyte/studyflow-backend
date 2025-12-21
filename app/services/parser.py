from ..schema.resource import Curriculum


class PydanticParserService:
    def parse_output(self, raw_output):
        parsed_output = Curriculum.model_validate(raw_output)
        
        return parsed_output
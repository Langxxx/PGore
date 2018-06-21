import getopt
import os
import sys
from xml.etree.ElementTree import parse
from jinja2 import Environment as JinjaEnvironment, FileSystemLoader
from abc import abstractclassmethod

all_entity = []


class LazyProperty:
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            value = self.func(instance)
            setattr(instance, self.func.__name__, value)
            return value


def camel_to_snake(camel_format):
    snake_format=''
    if isinstance(camel_format, str):
        pre_char_is_capital = False
        for index, _s_ in enumerate(camel_format):
            if _s_.islower():
                snake_format += _s_
                pre_char_is_capital = False
            else:
                if pre_char_is_capital:
                    snake_format += _s_.lower()
                else:
                    snake_format += _s_ if _s_.islower() else '_'+_s_.lower()
                pre_char_is_capital = True
    return snake_format


class BaseInfo:
    def __init__(self, attribute):
        self.user_info = {}
        self.name = attribute.attrib['name']
        self.is_optional = attribute.attrib.get('optional', False)
        if attribute and attribute[0].tag == 'userInfo':
            self.user_info = [entry.attrib for entry in attribute[0]]

    @abstractclassmethod
    def json_key(self):
        pass

    @LazyProperty
    def json_expression(self):
        if self.is_key_path:
            return "(json as AnyObject).value(forKeyPath: \"{json_key}\")".format(json_key=self.json_key)
        return "json[\"{json_key}\"]".format(json_key=self.json_key)

    @LazyProperty
    def is_key_path(self):
        return '.' in self.json_key


class Attribute(BaseInfo):
    def __init__(self, attribute):
        super(Attribute, self).__init__(attribute)
        self.type = attribute.attrib['attributeType'].replace('Integer ', 'Int')
        self.type = self.type if self.type != 'Boolean' else 'Bool'
        self.default_value = attribute.attrib.get('defaultValueString')

        if self.type == 'Bool' and self.default_value:
            self.default_value = 'true' if self.default_value == 'YES' else 'false'
        elif self.type == 'Binary':
            self.type = 'Data'
        elif self.type == 'String' and self.default_value:
            self.default_value = "\"{value}\"".format(value=self.default_value)

    def __str__(self):
        return """
                Attribute: {name}
                optional: {optional}
                type: {type}
                userInfo: {user_info}
        """.format(name=self.name, optional=self.is_optional, type=self.type, user_info=self.user_info)

    @property
    def json_value_expression(self):
        exp = self._json_value_expression()
        return exp if not self.default_value else exp + ' ?? ' + self.default_value

    @property
    def json_value_expression_for_check_null(self):
        return self._json_value_expression()

    def _json_value_expression(self):
        for entry in self.user_info:
            if entry['key'] == 'json_transformer' and entry['value']:
                return "{func}({json_exp})".format(func=entry['value'], json_exp=self.json_expression)
        if self.type.startswith('Int'):
            return "({json_exp} as? NSNumber)?.{type}Value"\
                .format(json_exp=self.json_expression,type=self.type.lower())
        else:
            return "{json_exp} as? {type}".format(json_exp=self.json_expression, type=self.type)

    @LazyProperty
    def json_ignore(self):
        if self.type == 'transient':
            return True
        else:
            for entry in self.user_info:
                if entry['key'] == 'json_ignore' and entry['value']:
                    return True
        return False

    @property
    def optional(self):
        if not self.is_optional:
            return ''
        for entry in self.user_info:
            if entry['key'] == 'force_unwrap':
                return '!'
        return '?'

    @LazyProperty
    def json_key(self):
        json_key = camel_to_snake(self.name)
        for entry in self.user_info:
            if entry['key'] == 'json_key' and entry['value']:
                json_key = entry['value']
        return json_key


class Relationship(BaseInfo):
    def __init__(self, relationship):
        super(Relationship, self).__init__(relationship)
        self.to_many = relationship.attrib.get('toMany', False)
        self.ordered = relationship.attrib.get('ordered', False)
        self.destination_entity = relationship.attrib.get('destinationEntity')

    def __str__(self):
        return """
                Relationship: {name}
                optional: {optional}
                toMany: {to_many}
                ordered: {ordered}
                userInfo: {user_info}
        """.format(name=self.name, optional=self.is_optional, to_many=self.to_many, ordered=self.ordered, user_info=self.user_info)

    @LazyProperty
    def json_key(self):
        for entry in self.user_info:
            if entry.get('key') == 'json_key':
                return entry['value']
        return None

    @property
    def json_value_expression(self):
        json_key = self.json_key
        if json_key and self.to_many:
            return "json[\"{k}\"] as? [JSONResponse]".format(k=json_key)
        elif json_key:
            return "json[\"{k}\"] as? JSONResponse".format(k=json_key)
        return None

    @LazyProperty
    def optional(self):
        if not self.is_optional:
            return ''
        for entry in self.user_info:
            if entry['key'] == 'force_unwrap':
                return '!'
        return '?'


class Entity:
    def __init__(self, entity):
        self.name = entity.attrib['name']
        self.attributes = [Attribute(_attr) for _attr in entity if _attr.tag == 'attribute']
        self.relationships = [Relationship(_attr) for _attr in entity if _attr.tag == 'relationship']
        self.parent_entity = entity.get('parentEntity')
        current_uniq_constraints = entity.find('uniquenessConstraints')
        if current_uniq_constraints:
            self.current_uniq_constraints = current_uniq_constraints[0][0].get('value')

    def __str__(self):
        return """
            Entity: {name}
            attributes:
                {attributes}
            relationships: {relationships}
        """.format(name=self.name, attributes=self.attributes, relationships=self.relationships)

    @LazyProperty
    def uniq_constraints_with_parent(self):
        if hasattr(self, 'current_uniq_constraints'):
            return self.current_uniq_constraints
        if self.parent_entity_obj:
            return self.parent_entity_obj.uniq_constraints_with_parent
        return None

    @LazyProperty
    def parent_entity_obj(self):
        for entity in all_entity:
            if entity.name == self.parent_entity:
                return entity
        return None

    @LazyProperty
    def all_attributes(self):
        parent_entity = self.parent_entity_obj
        if parent_entity:
            copy = self.attributes
            copy.extend(parent_entity.attributes)
            return copy
        return self.attributes

    @LazyProperty
    def all_relationships(self):
        parent_entity = self.parent_entity_obj
        if parent_entity:
            copy = self.relationships
            copy.extend(parent_entity.relationships)
            return copy
        return self.relationships


def parse_model(input):
    doc = parse(input)
    root = doc.getroot()
    entities = [Entity(entity) for entity in root if entity.tag == 'entity']
    return entities


def parse_args():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hi:o:t:', ['input=', 'output=', 'tmpl='])
    except getopt.GetoptError:
        print('Error: -i <inputfile> -o [outputfile]')
        print('or: -input <inputfile> -output [outputfile]')
        exit()

    template = 'tmpl'
    output_path = ''
    input_file = ''

    for opt, arg in opts:
        if opt == "-h":
            print('-i <inputfile> -o [outputfile] -t [template]')
            print('or: -input <inputfile> --output [outputfile] --tmpl [template]')
            exit()
        elif opt in ('-i', '--input'):
            input_file = arg
        elif opt in ('-o', '--output'):
            output_path = arg
        elif opt in ('-t', '--template'):
            template = arg

    if input_file and not output_path:
        output_path = os.path.dirname(input_file)

    if not input_file or not output_path:
        print('miss input file: -i <inputfile> or: -input <inputfile>')
        print('')

    return (input_file, output_path, template)


if __name__ == '__main__':
    input_file, output_path, template = parse_args()
    
    all_entity = parse_model(input_file)
    for entity in all_entity:
        output_name = output_path + entity.name + '+CoreDataProperties.swift'
        with open(output_name, 'wt') as f2:
            env = JinjaEnvironment(line_statement_prefix="#", loader=FileSystemLoader(
                searchpath=['./tmpl', template]
            ))
            tmpl = env.get_template('entity_extension.tmpl')
            text = tmpl.render(entity=entity)
            f2.write(text)
            print('generated ' + output_name)



import yaml

class Configuration(yaml.YAMLObject):
    yaml_tag = u'!Config'

    def __init__(self, batting_feats,
                       pitching_feats,
                       batting_intervals,
                       pitching_intervals,
                       input_path,
                       output_path,
                       log_path):
        self.batting_feats = batting_feats
        self.pitching_feats = pitching_feats
        self.batting_intervals = batting_intervals
        self.pitching_intervals = pitching_intervals
        self.input_path = input_path
        self.output_path = output_path
        self.log_path = log_path

    def __repr__(self):
        return """%s(batting_feats=%r,
                     pitching_feats=%r,
                     batting_intervals=%r,
                     pitching_intervals=%r,
                     input_path=%r,
                     output_path=%r,
                     log_path=%r)""" % (
                self.batting_feats,
                self.pitching_feats,
                self.batting_intervals,
                self.pitching_intervals,
                self.input_path,
                self.output_path,
                self.log_path)

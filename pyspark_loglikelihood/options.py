def normalize_options(options):
    """Normalize docopt's options dictionary."""
    _options = {}
    for k, v in options.iteritems():
        if k.startswith('<') and k.endswith('>') or k.startswith('--'):
            if k.startswith('<') and k.endswith('>'):
                k = k[1:-1]
            elif k.startswith('--'):
                k = k[2:]
            if k in ['help', 'version']:
                continue
            if k in ['fraction', 'threshold']:
                try:
                    v = float(v)
                except ValueError:
                    pass
            if any(x in k for x in ['num', 'size', 'count', 'min', 'max']):
                try:
                    v = int(v)
                except ValueError:
                    pass
            _options[k] = v
    return _options


__all__ = ['normalize_options']

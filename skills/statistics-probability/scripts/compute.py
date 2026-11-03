"""Small deterministic calculations; model selection remains the agent's responsibility."""
import json
import math
import statistics
import sys


def compute(request):
    if not isinstance(request, dict):
        raise ValueError('Request must be an object')
    operation = request.get('operation')
    if operation == 'describe':
        context = request.get('context')
        required = ('dataset_id', 'dataset_version', 'observation_unit', 'units')
        if not isinstance(context, dict) or any(
            not isinstance(context.get(k), str) or not context[k].strip() for k in required
        ):
            raise ValueError('Explicit dataset identity, version, observation unit and units required')
        if context.get('scope') not in ('sample', 'population'):
            raise ValueError('Explicit sample or population scope required')
        if context.get('variable_type') != 'quantitative':
            raise ValueError('Arithmetic summaries require quantitative values')
        values = request.get('values')
        if not isinstance(values, list) or not values or len(values) > 100000:
            raise ValueError('Supply 1 to 100000 numeric observations')
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
            raise ValueError('Missing, boolean, nonnumeric and nonfinite values require explicit treatment')
        variance = (statistics.variance(values) if len(values) > 1 else None) if context['scope'] == 'sample' else statistics.pvariance(values)
        modes = statistics.multimode(values)
        result = dict(context=context, n=len(values), mean=statistics.mean(values),
                      median=statistics.median(values), modes=[] if len(modes) == len(values) > 1 else modes,
                      range=max(values)-min(values), variance=variance,
                      sd=math.sqrt(variance) if variance is not None else None)
        result['mode_convention'] = 'All-unique data have no distinguished mode; repeated tied modes are retained'
        return result
    if operation == 'count':
        n, r = request.get('n'), request.get('r')
        if any(type(x) is not int or x < 0 or x > 1000 for x in (n, r)):
            raise ValueError('n and r must be integers from 0 through 1000')
        model = request.get('model')
        if model in ('ordered-distinct', 'unordered-distinct'):
            if r > n:
                raise ValueError('Selection without replacement requires r <= n')
            count = math.perm(n, r) if model == 'ordered-distinct' else math.comb(n, r)
        elif model == 'ordered-replacement':
            count = n ** r
        else:
            raise ValueError('Unknown counting model')
        return dict(model=model, n=n, r=r, count=count)
    raise ValueError('Unknown operation')


def main():
    try:
        with open(sys.argv[1], encoding='utf-8') as stream:
            result = compute(json.load(stream))
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    except (ValueError, TypeError, OSError, IndexError, OverflowError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

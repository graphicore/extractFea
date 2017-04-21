#! /usr/bin/env python

"""Generate an OpenType Feature file (fea) from an otf/ttf font."""

# TODO 1: add arguments to set up makeName: prefix, sufix

# TODO 2: Export one fea-file from multiple font sources. Especially merging
# GDEF clsses would be interesting. The other potential clashes can be solved
# by modifying the makeName function for each font.

# TODO 3: in ExportAggregator.validateLookup:
# Possible dependencies to other lookups:
#     GSUB type 5 Context (format 5.1 5.2 5.3)
#     GSUB type 6 Chaining Context (format 6.1 6.2 6.3)
#     GPOS type 7 Context positioning (format 7.1 7.2 7.3)
#     GPOS type 8 Chained Context positioning (format 7.1 7.2 7.3)
#
# GSUB contextuals: each of these have somewhere: an array of
# SubstLookupRecord which has a LookupListIndex into the GSUB LookupList
#
# GPOS contextuals: each of these have somewhere: an array of
# PosLookupRecord which has a LookupListIndex into the GPOS LookupList

# TODO 4: Better control over the languagesystem would be nice. Maybe just
# like: -r "languagsysten arab|latn *"
# Or, if not requested directly, activated like a dependency when the
# script plus language is being printed. But maybe without the option
# to block script/language output (like a "soft dependency"). Though, even
# if it is like a hard dependency we can still use --mute on it, so it's
# not a real problem to make it one
from __future__ import print_function, absolute_import
from fontTools.misc.py23 import *
from functools import wraps, partial
from .ft2fea import makeName, printFont

class ExportAggregator(object):
    """
    ExportAggregator provides a getStatus to use with the ft2fea print functions.

    It traverses the font tables and acquires status information for the
    relevant items. Once this traversal has been done, the getStatus method
    can be injected into the ft2fea print functions, that use the "getStatus"
    keyword argument.

    The actual status of an item is provided by the "getQueryStatus" method
    which is itself injetced into the constructor of this class.
    See the ExportQuery class.
    """


    def __init__(self, font, getQueryStatus):
        self.getQueryStatus = getQueryStatus
        self.font = font
        self.registry = {}
        self._transactions = []

    def getStatus(self, item, requiredState=None):


        noEntry = (None, None, False)
        if requiredState is not None:
            status= self.registry.get((item, requiredState), noEntry)
        else:
            # If there are any, the "True" values trump the "False" values
            # When requiredState is None and we check for both key types
            # i.e. (item, True) and (item, False)
            status = list(noEntry)
            for req in (True, False):
                key = (item, req)
                result, required, muted = self.registry.get(key, noEntry)
                status[0] = status[0] or result
                status[1] = status[1] or required
                status[2] = status[2] or muted
                if all(status):
                    # the result won't change anymore
                    break
        result, required, muted = status
        return (False if muted else result, required)

    # this is used as a decorator
    def register(func):
        @wraps(func)
        def wrapper(self, item, required, *args, **kwargs):
            # requiredKeyOverride: is used to run a validator with a different
            # required flag than the cache key will use. That way "validateLookup"
            # can declare lookupflag dependencies in GDEF. GDEF validation
            # needs to run after all potentially dependent validations.
            key = (item, kwargs.get('requiredKeyOverride', required))
            if 'requiredKeyOverride' in kwargs:
                del kwargs['requiredKeyOverride']
            registered = self.registry.get(key, None)
            if registered is not None:
                return registered
            # maybe it has been registered prior to this transaction
            for registry in reversed(self._transactions):
                registered = registry.get(key, None)
                if registered is not None:
                    return registered
            result = self.registry[key] = func(self, item, required, *args, **kwargs)
            return result
        return wrapper

    def _startTransaction(self):
        self._transactions.append(self.registry)
        self.registry = {}

    def _commitTransaction(self):
        registry = self._transactions.pop()
        registry.update(self.registry)
        self.registry = registry

    def _rollbackTransaction(self):
        self.registry = self._transactions.pop()

    def _validateSimpleEntry(self, selector, parentRequired):
        requestStatus, muted = self.getQueryStatus(*selector)
        required = requestStatus or parentRequired
        result = requestStatus is not False and (requestStatus or required) is True
        return (result, required, muted)

    # GDEF

    @register
    def validateMarkGlyphClassDef(self, glyphClassDef, parentRequired, table):
        selector = (table.tableTag, 'glyphClassDef')
        return self._validateSimpleEntry(selector, parentRequired)

    @register
    def validateAttachList(self, attachList, parentRequired, table):
        selector = (table.tableTag, 'attachList')
        return self._validateSimpleEntry(selector, parentRequired)

    @register
    def validateLigCaretList(self, ligCaretList, parentRequired, table):
        selector = (table.tableTag, 'ligCaretList')
        return self._validateSimpleEntry(selector, parentRequired)

    @register
    def validateMarkAttachmentClass(self, markAttachClassTuple, parentRequired, table):
        selector = (table.tableTag, 'markAttachClasses')
        return self._validateSimpleEntry(selector, parentRequired)

    @register
    def validateMarkAttachmentClassDef(self, markAttachmentClassDef, parentRequired, table):
        # This can't be (de-)selected directly so here's no selector check.
        # But, it's children can be selected using "GDEF markAttachClasses"
        # Which has the same effect. This way we can have the dependants
        # select just the required classes. See validateLookup
        required = parentRequired
        childCount = 0
        markAttachClassIDs = set(markAttachmentClassDef.classDefs.values())
        for markAttachClassID in markAttachClassIDs:
            # "All glyphs not assigned to a class fall into Class 0."
            # Thus there's no meaning in outputting this if it is ever present
            # It can't be referenced by a LookupFlag.
            if markAttachClassID == 0: continue
            # ad-hoc type to make it selectable
            markAttachClassTuple = (markAttachmentClassDef, markAttachClassID)
            success, _, _ = self.validateMarkAttachmentClass(markAttachClassTuple, required, table)
            if success:
                childCount += 1
        return (childCount > 0, required, False)

    @register
    def validateMarkGlyphSet(self, markGlyphSet_Coverage, parentRequired, table):
        selector = (table.tableTag, 'markGlyphSets')
        return self._validateSimpleEntry(selector, parentRequired)

    @register
    def validateMarkGlyphSetsDef(self, markGlyphSetsDef, parentRequired, table):
        # This can't be (de-)selected directly so here's no selector check.
        # But, it's children can be selected using "GDEF markGlyphSets"
        # which has the same effect. This way we can have the dependants
        # select just the required markSets. See validateLookup
        required = parentRequired
        childCount = 0
        for coverage in markGlyphSetsDef.Coverage:
            success, _, _ = self.validateMarkGlyphSet(coverage, required, table)
            if success:
                childCount += 1
        return (childCount > 0, required, False)

    @register
    def validateGDEF(self, table, parentRequired):
        requestStatus, muted = self.getQueryStatus(table.tableTag)
        required = requestStatus or parentRequired
        if requestStatus is False:
            return (False, required, muted)

        # check all dependencies
        childCount = 0
        children = [
            (self.validateMarkGlyphClassDef, table.table.GlyphClassDef),
            (self.validateAttachList, table.table.AttachList),
            (self.validateLigCaretList, table.table.LigCaretList),
            (self.validateMarkAttachmentClassDef, table.table.MarkAttachClassDef)
        ]
        if hasattr(table.table, 'MarkGlyphSetsDef'):
            children.append((self.validateMarkGlyphSetsDef, table.table.MarkGlyphSetsDef))

        for validate, item in children:
            if item is None:
                continue
            success, _, _ = validate(item, required, table)
            if success:
                childCount += 1
        return (childCount > 0, required, muted)

    # GPOS and GSUB
    @register
    def validateLookup(self, lookup, parentRequired, table):
        class Invalidation(Exception): pass
        # it has not really a tag, so we make one up
        # gpos3 is GPOS LookupType 3
        # gsub2 is GSUB LookupType 2 etc
        tag = '{0}{1}'.format(table.tableTag.lower(), lookup.LookupType)
        requestStatus, muted = self.getQueryStatus(table.tableTag, 'lookup', tag)
        required = requestStatus or parentRequired
        if requestStatus is False or not required:
            return (False, required, muted)
        # required is true, check dependencies:
        self._startTransaction()
        invalid = False
        # using try/catch so that the transaction can be finalized properly
        # via either commit or rollback
        try:
            # check the lookupFlag
            # 0x10 UseMarkFilteringSet
            if lookup.LookupFlag & 0x10:
                # don't validate if the table is blocked
                if self.getQueryStatus('GDEF')[0] is False:
                    raise Invalidation
                gdef = self.font['GDEF']
                coverage = gdef.table.MarkGlyphSetsDef.Coverage[lookup.MarkFilteringSet]
                success, _, _ = self.validateMarkGlyphSet(coverage, True, gdef, requiredKeyOverride=False)
                if not success:
                    raise Invalidation

            # MarkAttachmentType
            markAttachClassID = lookup.LookupFlag >> 8
            if markAttachClassID:
                # don't validate if the table is blocked
                if self.getQueryStatus('GDEF')[0] is False:
                    raise Invalidation
                gdef = self.font['GDEF']
                # An ad-hoc pseudo item, to enable outputting just the used
                # mark attachment classes
                markAttachClassTuple = (gdef.table.MarkAttachClassDef, markAttachClassID)
                success, _, _ = self.validateMarkAttachmentClass(markAttachClassTuple, True, gdef, requiredKeyOverride=False)
                if not success:
                    raise Invalidation


            # TODO 3: in ExportAggregator.validateLookup:
            # Possible dependencies to other lookups:
            #     GSUB type 5 Context (format 5.1 5.2 5.3)
            #     GSUB type 6 Chaining Context (format 6.1 6.2 6.3)
            #     GPOS type 7 Context positioning (format 7.1 7.2 7.3)
            #     GPOS type 8 Chained Context positioning (format 7.1 7.2 7.3)

            # FIXME: this is incomplete, only GSUB 6.3 is finished
            if table.tableTag == 'GSUB' and lookup.LookupType in (5, 6):
                for sub in lookup.SubTable:
                    if lookup.LookupType == 6 and sub.Format == 3:
                        # type6: sub === ChainContextSubst
                        for slr in sub.SubstLookupRecord:
                            lookupDependency = table.table.LookupList.Lookup[slr.LookupListIndex]
                            success, _, _ = self.validateLookup(lookupDependency, True, table, requiredKeyOverride=False)
                            if not success:
                                raise Invalidation
            # if table.tableTag == 'GPOS' and lookup.LookupType in (7, 8):


        except Invalidation:
            invalid = True
        except Exception as e:
            invalid = True
            raise e
        finally:
            if invalid:
                self._rollbackTransaction()
                result = (False, True, muted)
            else:
                self._commitTransaction()
                result = (True, True, muted)
        return result

    @register
    def validateFeatureRecord(self, featureRecord, parentRequired, table):
        requestStatus, muted = self.getQueryStatus(table.tableTag, 'feature', featureRecord.FeatureTag)
        required = requestStatus or parentRequired
        if requestStatus is False:
            return (False, required, muted)

        # check all dependencies
        childCount = 0
        for lookupIdx in featureRecord.Feature.LookupListIndex:
            # get the lookup from the lookupList
            lookup = table.table.LookupList.Lookup[lookupIdx]
            success, _, _ = self.validateLookup(lookup, required, table)
            if success:
                childCount += 1
        return (childCount > 0, required, muted)

    @register
    def validateLanguage(self, langTuple, parentRequired, table):
        langTag, langSys = langTuple
        requestStatus, muted = self.getQueryStatus(table.tableTag, 'language', langTag)
        required = requestStatus or parentRequired
        if requestStatus is False:
            return (False, required, muted)

        # check all dependencies
        childCount = 0
        for featureIdx in langSys.FeatureIndex:
            featureRecord = table.table.FeatureList.FeatureRecord[featureIdx]
            success, _, _ = self.validateFeatureRecord(featureRecord, required, table)
            if success:
                childCount += 1
        return (childCount > 0, required, muted)

    @register
    def validateScriptRecord(self, scriptRecord, parentRequired, table):
        requestStatus, muted = self.getQueryStatus(table.tableTag, 'script', scriptRecord.ScriptTag)
        required = requestStatus or parentRequired
        if requestStatus is False:
            return (False, required, muted)
        # check all dependencies
        childCount = 0
        if scriptRecord.Script.DefaultLangSys is not None:
            lang = ('dflt', scriptRecord.Script.DefaultLangSys)
            success, _, _ = self.validateLanguage(lang, required, table)
            if success:
                childCount += 1

        for langSysRecord in scriptRecord.Script.LangSysRecord:
            # Use tuples, as they register fine within the registry dict
            # and they can be recreated later without loosing identity.
            # This way I don't need to branch validateLanguage for DefaultLangSys
            # (see above) which has no DefaultLangSysRecord or a simmilar
            # that features LangSysTag and LangSys (DefaultLangSys is
            # equivalent to LangSys) The rendering code will have to
            # recreate these tuples as well, to read the registry status.
            lang = (langSysRecord.LangSysTag, langSysRecord.LangSys)
            success, _, _ = self.validateLanguage(lang, required, table)
            if success:
                childCount += 1
        return (childCount > 0, required, muted)

    @register
    def validateCommonGTable(self, table, parentRequired):
        assert table.tableTag in {'GPOS', 'GSUB'}, 'Wrong table type: {0}'.format(table.tableTag)
        requestStatus, muted = self.getQueryStatus(table.tableTag)
        required = requestStatus or parentRequired
        if requestStatus is False:
            return (False, required, muted)
        # check all dependencies
        childCount = 0
        for scriptRecord in table.table.ScriptList.ScriptRecord:
            sucess, _, _ = self.validateScriptRecord(scriptRecord, required, table)
            if sucess:
                childCount += 1
        # No need to do features here, as they are fully dependent on the script
        # records.

        # Lookups can be outputted without script/lang/feature and that can be
        # requested so.
        for lookup in table.table.LookupList.Lookup:
            success, _, _ = self.validateLookup(lookup, False, table)
            if success:
                childCount += 1
        return (childCount > 0, required, muted)

    @register
    def validateLanguagesystem(self, itemString, parentRequired):
        # NOTE: item is really just a string, as there is not an
        # item for the languagesystem definition in fea files, since a
        # string can be reproduced, identitywise, this works just fine.
        selector = (itemString, ) # one string in a tuple
        return self._validateSimpleEntry(selector, parentRequired)

    def validate(self, required=False):
        self.validateLanguagesystem('languagesystem', required)

        for tableTag in ('GPOS', 'GSUB'):
            if tableTag in self.font:
                self.validateCommonGTable(self.font[tableTag], required)
        if 'GDEF' in self.font:
            self.validateGDEF(self.font['GDEF'], required)

class Selector(object):
    def __init__(self, string):
        self._rules = self.parse(string)

    def parse(self, string):
        rules = [[{ z for z in y.split('|') if len(z)} # set comprehension, no empty entries
                        for y in x.strip().split()] # split without argument splits on whitespace
                            for x in string.split(';')] # rules are separated by semicolons
        result = []
        for rule in rules:
            if not len(rule):
                continue
            for i,entry in enumerate(rule):
                if not len(entry):
                    # the rule won't select anything
                    rule = None
                    break
                # remove everything after "**"
                if '**' in entry:
                    # so we can later sort the rules by length ???? (if it makes sense)
                    del rule[i + 1:]
            if rule is not None:
                result.append(rule)
        # shortest rule first, may speed up selecting a bit
        result.sort(cmp=lambda x,y:len(x)-len(y))
        return result;

    def _ruleSelects(self, rule, item):
        if len(rule) == 0 \
                or len(rule) > len(item) \
                or len(rule) < len(item) and "**" not in rule[-1]:
            return False

        for entry, name in zip(rule, item):
            if '**' in entry:
                # validates all the rest of item, no matter what the content
                break
            elif '*' in entry:
                continue
            elif name not in entry:
                return False
        return True

    def __contains__(self, item):
        for rule in self._rules:
            if self._ruleSelects(rule, item):
                return True
        return False

class ExportQuery(object):
    def __init__(self, request=None, whitelist=None, blacklist=None, mute=None, **kwargs):

        self._request = Selector(request) \
                            if request is not None else None
        self._whitelist = Selector(whitelist) \
                            if whitelist is not None else None
        self._blacklist = Selector(blacklist) \
                            if blacklist is not None else None
        self._mute = Selector(mute) \
                            if mute is not None else None

    def getQueryStatus(self, *item):
        """ Return the query state of the item; True, False or None:
                True: Item is requested
                False: Item is blocked
                None: Item may be exported, if a dependent item requires it
        """
        muted = self._mute is not None and item in self._mute
        if (self._whitelist is not None and item not in self._whitelist) \
                or (self._blacklist is not None and item in self._blacklist):
            return (False, muted)
        # if request is None, the default is to select everything
        if self._request is None or item in self._request:
            return (True, muted)
        return (None, muted) # Maybe



    # font = TTFont(args.font)
    # query = ExportQuery(**{arguments dictionary})
    # extract(font, query, suffix=args.suffix or '')
def extract(font, query, suffix='', print=print):
    aggregator = ExportAggregator(font, query.getQueryStatus)
    aggregator.validate()

    printFont(font,
              makeName=partial(makeName, uniquenessDict={}, suffix=suffix),
              getStatus=aggregator.getStatus, print=print)

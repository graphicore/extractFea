The tool outputs GDEF, GPOS and GSUB. However, I only implemented the GPOS Lookup Types 4, 5 and 6 (MarkToBase, MarkToLigature, MarkToMark) yet.

The command line tool features a  query api that makes it possible to export just selected parts of the fea and honors dependency relations (like a Lookupflag that requires a defined Mark Attachment Class from GDEF) .

[Sample output of `$ ft2feaCLI.py fontfile.otf > dumped.fea`](https://gist.github.com/graphicore/fb2a314ed8e91be65e5a)

The help output of the tool:

```
$ ./ft2feaCLI.py -h
usage: ft2feaCLI.py [-h] [-r, --request [REQUEST]]
                    [-w, --whitelist [WHITELIST]]
                    [-b, --blacklist [BLACKLIST]] [-m, --mute [MUTE]]
                    FONT-PATH

Generate an OpenType Feature file (fea) from an otf/ttf font.

positional arguments:
  FONT-PATH             A ttf or otf OpenType font file.

optional arguments:
  -h, --help            show this help message and exit
  -r, --request [REQUEST]
                        Select the fea contents to export. Default: "**"
  -w, --whitelist [WHITELIST]
                        Whitelist fea contents.
  -b, --blacklist [BLACKLIST]
                        Blacklist fea contents.
  -m, --mute [MUTE]     Mute the printed output of fea contents.

The --request, --whitelist, --blacklist and --mute options; all take
as argument the same type of selector definition, which specifies the
the members of each set. See "The Selector Specification" below.

-r, --request
      Define the items that should be exported. If no request is
      defined (default) all items are requested (like: -r "**").
      If an empty request is defined (like: -r "") no item is requested.
      Items that are not directly requested are marked as "Maybe"
      which means that they are exported if they are a dependency
      of other items.
      E.g.: Lookups are dependencies of features. In order to export
      a feature, the lookups of the feature will be exported as well.
      If all of its lookups are are filtered (by --whitelist
      or --blacklist) the feature will not be exported even if it
      was requested.
      Similarly, LookupFlags of lookups can make a lookup dependent
      on the GDEF items "markAttachClasses" (Flag: MarkAttachmentType)
      and/or "markGlyphSets" (Flag: UseMarkFilteringSet) and some
      Lookup Types can themselves be dependent on other Lookups in
      the same table (GDEF or GPOS).
      NOTE: These Lookup Types are not yet implemented.

-w, --whitelist
      If a whitelist is present only items that are selected
      by the whitelist are allowed for output. This also means that
      this can block other not directly blocked items from output,
      if their dependencies are blocked.
      (default is like: -w "**")

-b, --blacklist
      If a blacklist is present only items that are *NOT* selected
      by the blacklist are allowed for output. his also means that
      this can block other not directly blocked items from output,
      if their dependencies are blocked.

-m, --mute
      While --whitelist and --blacklist try to keep the fea output
      valid when blocking other items (by taking care of dependencies)
      mute is not that careful. Mute allows to select items to not
      being printed, while dependent items will still be outputted.
      This is useful e.g. in a build process if all lookups of a
      feature should be used, but the features itself and thus the
      application of it are predefined somewhere else.
      E.g.: -r "GPOS feature mkmk" -m "GPOS feature mkmk" will output
      only the lookups used by the mkmk feature and if needed some
      class definitions of the GDEF table for Lookup-Flags. But
      the feature definition "feature mkmk { ... } mkmk;" will be
      omitted.
      Another scenario may be the inspection of the dependencies of an item
      while shutting of other noise.

The Selector Specification
==========================

A "selector" is made up of one or more single selectors, separated by
semicolons: "single-selector;single-selector;single-selector;

A "single-selector" is made up of one or more "selector-parts", separated
by whitespace: "part1 part2 part3". These parts represent a parent-child
like hierarchy: part3 is contained in part2 and part2 is contained in
part1.

A "selector-part" is made up of one ore more "selector-tags", separated
by the pipe "|" symbol:  "tag1|tag2|tag3". Each part of a tag represents
an alternative (logical OR) on the hierarchy level of the "selector-part"

Selector-Tags
-------------

"*" and "**" are wildcard tags.

"*" selects all items on the current hierarchy level. Thus it's not
    needed to have further tags separated with "|" in the same selector-part
"**" selects all items on the current hierarchy level and on all hierarchy
     levels below. Thus after a "**" it's not needed to add any further
     parts to select deeper levels. A single-selector ends after the
     first "**"

### Available tags and their hierarchy level (by indentation)

  languagesystem
  GDEF
      glyphClassDef
      attachList
      ligCaretList
      markAttachClasses
      markGlyphSets
  GSUB and GPOS
      script
          DFLT latn arab ... [script tags]
      language
          DEU dflt ARA URD ... [language tags]
      feature
          mkm mark calt dlig liga init medi ... [feature tags]
      lookup
          gpos1 gsub2 ... [see 'Lookup Type Selector Tags' below]// gpos1

 ### Lookup Type Selector Tags:
 from: https://www.microsoft.com/typography/otspec/gpos.htm

     gpos1: Single adjustment (GPOS Lookup-Type 1)
     gpos2: Pair adjustment
     gpos3: Cursive attachment
     gpos4: MarkToBase attachment
     gpos5: MarkToLigature attachment
     gpos6: MarkToMark attachment
     gpos7: Context positioning
     gpos8: Chained Context positioning
     gpos9: Extension positioning
     gsub1: Single
     gsub2: Multiple
     gsub3: Alternate
     gsub4: Ligature
     gsub5: Context
     gsub6: Chaining Context
     gsub7: Extension Substitution
     gsub8: Reverse chaining context single

EXAMPLES
========

$ fea2ft path/to/font.otf > features.fea
    Export all features of font.otf and save them to the file features.fea

$ fea2ft -r "GPOS" path/to/font.otf
    export just the GPOS table and GDEF dependencies if there.

$ ft2fea -r "GPOS feature mkmk|mark" path/to/font.otf
    export the mkmk and mark feature of the GPOS table (if available)

$ ft2fea -r "* script DFLT" path/to/font.otf
    export everything registered under the DFLT script

$ ft2fea -r "languagesystem" path/to/font.otf
    Print all languagesystem definitions for the font.
    NOTE: control over "languagesystem" is very limited at the moment.
    It is is not used as a dependency of script and language, thus all
    languagesystem definitions are either printed or not.

$ ft2fea -r "GSUB feature medi" -m "GDEF; GSUB feature *" path/to/font.otf
    export the lookups used by the medi feature of GSUB

$ ft2fea -r "GPOS lookup gpos4|gpos5|gpos6" path/to/font.otf
    export only the lookups of type MarkToBase (gpos4) or
    MarkToLigature (gpos5) or MarkToMark(gpos6)

$ ft2fea -r "* * gpos4|gpos5|gpos6" path/to/font.otf
    export only the lookups of type MarkToBase (gpos4) or
    MarkToLigature (gpos5) or MarkToMark(gpos6). Note, nothing but
    "GPOS ligature" as children named like "gpos4", thus the wildcards
    do just fine.

$ ft2fea -request "GPOS|GSUB feature *" \
            -whitelist "GPOS|GSUB; GPOS|GSUB **" \
            -mute "* feature *"  \
            path/to/font.otf
    Select features of GPOS or GSUB but filter dependencies that are not
    in GPOS or GSUB, i.e. lookups depending on class definitions in GDEF.
    Mute the feature blocks, so that only the lookups are exported.

```


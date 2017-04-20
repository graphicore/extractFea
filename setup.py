from setuptools import setup

setup(name='extraxtfea',
      version='0.1',
      description='Write an Adobe FEA file from binary font data.',
      url='http://github.com/graphicore/extraxtFea',
      author='Lasse Fister',
      author_email='commander@graphicore.de',
      license='APACHE2',
      package_dir={'': 'Lib'}
      packages=['extractFea'],
      install_requires=[
          'fonttools',
      ],
      scripts=['Lib/extractFea/bin/extract-fea'],
      zip_safe=False)

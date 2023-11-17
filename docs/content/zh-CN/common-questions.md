# 常见问题


### Q1: 北冥坞系统如何保护用户数据隐私？

A1: 在北冥坞系统中，学件的上传、查搜、部署均无需用户上传本地数据。所有涉及的统计规约均由用户本地生成，并不会暴露原始数据，以确保您的数据隐私。


### Q2: 北冥坞系统如何确保用户部署学件的安全？

A2: 我们会尽最大努力检验每个学件的安全，并提供在 `docker` 容器内调用和部署学件的接口。


### Q3: 北冥坞系统支持哪些数据类型的学件？

A3: 我们支持多种数据类型，包括表格、图像和文本。


### Q4: 如何开启异构表格查搜？

A4: 当常规查搜返回空列表时，系统会提示您开启异构查搜。您需要额外提供每一维度特征的语义信息，可以手动填写或上传包含特征语义信息的 `json` 文件，然后进行查搜。


### Q5: 学件上传后为什么没有在系统中显示？

A5: 学件上传后，系统会自动将其加入验证队列检验其是否符合规范，包括学件格式以及模型功能的检查。验证结果将在网页端「个人信息 - 我的学件」处显示，只有验证通过才会在系统中显示。为提高通过率，建议您在上传前使用 `learnware` 包对学件进行本地验证。